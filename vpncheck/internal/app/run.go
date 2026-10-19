package app

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/redact"
	"github.com/RuNick7/vpn-check/internal/report"
	"github.com/RuNick7/vpn-check/internal/site"
	"github.com/RuNick7/vpn-check/internal/source"
	"github.com/RuNick7/vpn-check/internal/subscription"
)

// What a run is doing, as the page shows it.
const (
	phaseIdle     = "idle"
	phaseFetching = "fetching" // the computer's own connection, then the subscription
	phaseNetwork  = "network"  // DNS, ports and TLS of every server at once
	phaseTunnels  = "tunnels"  // through each server, one after another
	phaseDone     = "done"
	phaseFailed   = "failed" // the subscription itself is the trouble
	phaseStopped  = "stopped"
)

// run is one check of one link. The goroutine doing it writes its fields
// under App.mu; the page reads them through state.
type run struct {
	link   string
	opts   check.Options
	cancel context.CancelFunc
	red    *redact.Redactor
	rep    *report.Report

	phase    string
	problem  *Problem
	card     *Card
	vpn      string
	internet bool
	targets  []*subscription.Target
	groups   []group
	reached  []bool
	results  []*check.Result
	current  int
	files    *report.Files
	archive  string
	saved    string
	// What the site says the subscription is; nil when it was not asked or
	// did not answer.
	status  *site.Status
	sending bool
	sent    *site.Sent
}

func (r *run) active() bool {
	return r.phase == phaseFetching || r.phase == phaseNetwork || r.phase == phaseTunnels
}

// sendable reports whether the report can go to support: a run that has
// finished, of a link the site can find the customer by, whose subscription
// has not simply run out -- that needs paying, not support.
func (r *run) sendable() bool {
	if r.active() || r.files == nil || !isWebLink(r.link) {
		return false
	}
	return r.status == nil || (r.status.State != "expired" && r.status.State != "none")
}

func isWebLink(link string) bool {
	lower := strings.ToLower(link)
	return strings.HasPrefix(lower, "https://") || strings.HasPrefix(lower, "http://")
}

// group is one profile as an app lists it: what the customer picks in Happ.
// A profile is a balancer over servers, so it works while any of them does.
type group struct {
	name    string
	servers []int
}

func groupsOf(profiles []subscription.Profile, targets []*subscription.Target) []group {
	var groups []group
	index := map[string]int{}
	for _, profile := range profiles {
		if _, seen := index[profile.Name]; seen {
			continue
		}
		index[profile.Name] = len(groups)
		groups = append(groups, group{name: profile.Name})
	}
	for i, target := range targets {
		for _, name := range target.Profiles {
			if g, ok := index[name]; ok {
				groups[g].servers = append(groups[g].servers, i)
			}
		}
	}
	return groups
}

// start begins a check of link, replacing whatever run came before.
func (a *App) start(link string, opts check.Options) {
	ctx, cancel := context.WithCancel(context.Background())
	r := &run{link: link, opts: opts, cancel: cancel, red: redact.New(), rep: report.New(a.cfg.Version), phase: phaseFetching, current: -1}
	if a.cfg.Platform != "" {
		r.rep.Platform = a.cfg.Platform
	}
	a.mu.Lock()
	a.run = r
	a.runs++
	a.mu.Unlock()
	go a.execute(ctx, r)
}

func (a *App) update(change func()) {
	a.mu.Lock()
	defer a.mu.Unlock()
	change()
}

func (a *App) execute(ctx context.Context, r *run) {
	opts := r.opts
	opts.RunID = r.rep.RunID
	// The site's word on payment, asked alongside everything else.
	status := make(chan *site.Status, 1)
	go func() { status <- a.askStatus(ctx, r.link) }()

	// The computer's own connection first: with no internet, or another VPN
	// running, nothing after it means what it seems to.
	r.rep.Baseline, r.rep.Clock = check.Baseline(ctx, opts)
	internet, vpn := true, ""
	for _, step := range r.rep.Baseline {
		switch step.Name {
		case "Интернет без VPN":
			internet = step.Status == check.OK
		case "Другой VPN":
			vpn = check.ActiveTunnel()
		}
	}
	a.update(func() { r.internet, r.vpn = internet, vpn })

	src, profiles := source.Load(ctx, r.link, a.cfg.UserAgent, r.red)
	r.rep.Sources = []report.Source{src}
	if ctx.Err() != nil {
		a.finish(r, phaseStopped, nil)
		return
	}
	now := time.Now()
	st := <-status
	targets := subscription.Targets(profiles)
	r.rep.Total = len(targets)
	a.update(func() {
		r.status = st
		r.card = cardFor(src, len(profiles), now, st, a.cfg.Site != "")
		r.targets = targets
		r.groups = groupsOf(profiles, targets)
		r.reached = make([]bool, len(targets))
		r.results = make([]*check.Result, len(targets))
		r.phase = phaseNetwork
	})
	if problem := statusProblem(st); problem != nil {
		a.finish(r, phaseFailed, problem)
		return
	}
	if problem := subscriptionProblem(src, internet, now); problem != nil {
		a.finish(r, phaseFailed, problem)
		return
	}
	if src.Servers > 0 {
		a.remember(r.link)
	}

	results := check.NewRunner(opts).Watch(check.Progress{
		Network: func(i int) { a.update(func() { r.reached[i] = true }) },
		Tunnel:  func(i int) { a.update(func() { r.phase, r.current = phaseTunnels, i }) },
	}).Run(ctx, targets, func(i int, result *check.Result) {
		a.update(func() { r.results[i] = result })
	})
	r.rep.Results = results
	if ctx.Err() != nil {
		a.finish(r, phaseStopped, nil)
		return
	}
	a.finish(r, phaseDone, nil)
}

// finish writes the report, so that whatever the run found -- a subscription
// that would not download included -- can be saved and sent.
func (a *App) finish(r *run, phase string, problem *Problem) {
	r.rep.Finished = time.Now()
	files, err := report.Write(a.cfg.Dir, r.rep, r.red)
	if err != nil {
		problem = &Problem{Title: "Не удалось сохранить отчёт", Text: r.red.String(err.Error())}
		phase = phaseFailed
	}
	a.update(func() {
		r.files, r.phase, r.problem, r.current = files, phase, problem, -1
	})
	pruneRuns(a.cfg.Dir, keepRuns)
}

// askStatus asks the site what the subscription is. Nil when there is no
// site to ask or it does not answer: the check goes on without it.
func (a *App) askStatus(ctx context.Context, link string) *site.Status {
	if a.cfg.Site == "" || !isWebLink(link) {
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	status, err := site.New(a.cfg.Site).Status(ctx, link)
	if err != nil {
		return nil
	}
	return status
}

// statusProblem stops a check of a subscription that has run out: nothing
// to find on the servers, and the answer is to pay.
func statusProblem(st *site.Status) *Problem {
	if st == nil {
		return nil
	}
	switch st.State {
	case "expired":
		title := "Подписка закончилась"
		if st.ExpiresAt != nil {
			title += " " + day(time.Unix(*st.ExpiresAt, 0))
		}
		return &Problem{Title: title, Text: "Поэтому VPN и не подключается. Продлите её, и серверы заработают сами — проверять ничего не нужно.",
			Link: st.RenewURL, LinkText: "Продлить"}
	case "none":
		return &Problem{Title: "Подписка не оплачена", Text: "По этой ссылке ещё не было оплаченного времени. Оформите подписку, и серверы заработают.",
			Link: st.RenewURL, LinkText: "Оформить"}
	}
	return nil
}

// subscriptionProblem says why a subscription gives nothing to check, or nil
// when it has servers.
func subscriptionProblem(src report.Source, internet bool, now time.Time) *Problem {
	switch {
	case src.Status == 0 && src.Error != "":
		if !internet {
			return &Problem{Title: "Нет интернета", Text: "Интернет не работает даже без VPN. Проверьте подключение и запустите проверку снова."}
		}
		return &Problem{Title: "Подписка не скачалась",
			Text: "Сервер подписок не ответил с этого интернета. Сохраните отчёт и пришлите его в поддержку: по нему видно, что именно не так."}
	case src.Status == http.StatusNotFound:
		return &Problem{Title: "Подписка не найдена",
			Text: "По этой ссылке подписки нет. Если ссылку сбрасывали в боте, старая больше не работает: скопируйте новую в боте или личном кабинете."}
	case src.Status != http.StatusOK:
		return &Problem{Title: "Сервер подписок ответил ошибкой",
			Text: fmt.Sprintf("Код ответа %d. Попробуйте через несколько минут; если не пройдёт, пришлите отчёт в поддержку.", src.Status)}
	case src.Servers > 0:
		return nil
	}
	for name, value := range src.Notices {
		if strings.Contains(name, "limit") || strings.Contains(name, "max-devices") {
			if v := strings.ToLower(value); v != "" && v != "false" && v != "0" {
				return &Problem{Title: "Все места для устройств заняты",
					Text: "Проверка считается отдельным устройством «vpncheck». Удалите ненужное устройство в боте и запустите проверку снова."}
			}
		}
	}
	if info, ok := report.ParseUserInfo(src.UserInfo); ok && !info.Expire.IsZero() && info.Expire.Before(now) {
		return &Problem{Title: "Подписка закончилась " + day(info.Expire),
			Text: "Поэтому VPN и не подключается. Продлите её в боте или личном кабинете."}
	}
	if src.Format == "" {
		return &Problem{Title: "Подписка не читается", Text: src.Error + ". Пришлите отчёт в поддержку."}
	}
	text := "Панель не выдала ни одного сервера. Пришлите отчёт в поддержку."
	if announce := src.Notices["announce"]; announce != "" {
		text = "Панель передаёт: «" + announce + "». " + text
	}
	return &Problem{Title: "В подписке нет серверов", Text: text}
}

// Card is the subscription as the top of the check screen shows it.
type Card struct {
	Title    string `json:"title"`
	Status   string `json:"status,omitempty"`
	Tone     string `json:"tone,omitempty"`
	Traffic  string `json:"traffic,omitempty"`
	Servers  int    `json:"servers"`
	Profiles int    `json:"profiles"`
	// A line under the card: the free tier, or that payment is unknown.
	Note string `json:"note,omitempty"`
}

// The FREE tier keeps every panel account years ahead and holds the real end
// date in our own database; a date this far out says nothing about payment.
const farExpiry = 2 * 365 * 24 * time.Hour

// cardFor draws the subscription from the panel's headers, with the site's
// status in place of the panel's date when there is one.
func cardFor(src report.Source, profiles int, now time.Time, st *site.Status, asked bool) *Card {
	card := &Card{Title: src.Title, Servers: src.Servers, Profiles: profiles}
	if card.Title == "" {
		card.Title = "Подписка"
	}
	info, ok := report.ParseUserInfo(src.UserInfo)
	if ok {
		card.Traffic = "Трафик " + gigabytes(info.Used)
		if info.Total > 0 {
			card.Traffic += " из " + gigabytes(info.Total)
		}
	}
	if st != nil {
		statusOf(card, st, now)
		return card
	}
	if asked {
		card.Note = "Статус оплаты уточнить не удалось."
	}
	if !ok {
		return card
	}
	switch left := info.Expire.Sub(now); {
	case info.Expire.IsZero() || left > farExpiry:
		card.Status, card.Tone = "Активна", "ok"
	case left <= 0:
		card.Status, card.Tone = "Закончилась "+day(info.Expire), "bad"
	case left < 3*24*time.Hour:
		card.Status, card.Tone = "Заканчивается "+day(info.Expire), "warn"
	default:
		card.Status, card.Tone = "Активна до "+day(info.Expire), "ok"
	}
	return card
}

func statusOf(card *Card, st *site.Status, now time.Time) {
	var expires time.Time
	if st.ExpiresAt != nil {
		expires = time.Unix(*st.ExpiresAt, 0)
	}
	switch st.State {
	case "active":
		switch {
		case expires.IsZero():
			card.Status, card.Tone = "Активна", "ok"
		case expires.Sub(now) < 3*24*time.Hour:
			card.Status, card.Tone = "Заканчивается "+day(expires), "warn"
		default:
			card.Status, card.Tone = "Активна до "+day(expires), "ok"
		}
	case "free":
		card.Status, card.Tone = "Бесплатный тариф", "warn"
		card.Note = "Бесплатный тариф: доступна часть серверов."
	case "expired":
		card.Status, card.Tone = "Закончилась", "bad"
		if !expires.IsZero() {
			card.Status += " " + day(expires)
		}
	case "none":
		card.Status, card.Tone = "Не оплачена", "bad"
	}
}

var months = []string{"января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"}

func day(t time.Time) string {
	return fmt.Sprintf("%d %s %d", t.Day(), months[t.Month()-1], t.Year())
}

func gigabytes(n int64) string {
	gb := float64(n) / (1 << 30)
	if gb < 10 {
		return strings.Replace(fmt.Sprintf("%.1f ГБ", gb), ".", ",", 1)
	}
	return fmt.Sprintf("%.0f ГБ", gb)
}

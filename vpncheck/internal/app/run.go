package app

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/check"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/redact"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/report"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/source"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/subscription"
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
}

func (r *run) active() bool {
	return r.phase == phaseFetching || r.phase == phaseNetwork || r.phase == phaseTunnels
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
func (a *App) start(link string) {
	ctx, cancel := context.WithCancel(context.Background())
	r := &run{link: link, cancel: cancel, red: redact.New(), rep: report.New(a.cfg.Version), phase: phaseFetching, current: -1}
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
	opts := a.cfg.Options
	opts.RunID = r.rep.RunID
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
	targets := subscription.Targets(profiles)
	r.rep.Total = len(targets)
	a.update(func() {
		r.card = cardFor(src, len(profiles), now)
		r.targets = targets
		r.groups = groupsOf(profiles, targets)
		r.reached = make([]bool, len(targets))
		r.results = make([]*check.Result, len(targets))
		r.phase = phaseNetwork
	})
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
		problem = &Problem{"Не удалось сохранить отчёт", r.red.String(err.Error())}
		phase = phaseFailed
	}
	a.update(func() {
		r.files, r.phase, r.problem, r.current = files, phase, problem, -1
	})
	pruneRuns(a.cfg.Dir, keepRuns)
}

// subscriptionProblem says why a subscription gives nothing to check, or nil
// when it has servers.
func subscriptionProblem(src report.Source, internet bool, now time.Time) *Problem {
	switch {
	case src.Status == 0 && src.Error != "":
		if !internet {
			return &Problem{"Нет интернета", "Этот компьютер не выходит в интернет даже без VPN. Проверьте подключение и запустите проверку снова."}
		}
		return &Problem{"Подписка не скачалась",
			"Сервер подписок не ответил с этого интернета. Сохраните отчёт и пришлите его в поддержку: по нему видно, что именно не так."}
	case src.Status == http.StatusNotFound:
		return &Problem{"Подписка не найдена",
			"По этой ссылке подписки нет. Если ссылку сбрасывали в боте, старая больше не работает: скопируйте новую в боте или личном кабинете."}
	case src.Status != http.StatusOK:
		return &Problem{"Сервер подписок ответил ошибкой",
			fmt.Sprintf("Код ответа %d. Попробуйте через несколько минут; если не пройдёт, пришлите отчёт в поддержку.", src.Status)}
	case src.Servers > 0:
		return nil
	}
	for name, value := range src.Notices {
		if strings.Contains(name, "limit") || strings.Contains(name, "max-devices") {
			if v := strings.ToLower(value); v != "" && v != "false" && v != "0" {
				return &Problem{"Все места для устройств заняты",
					"Проверка считается отдельным устройством «vpncheck». Удалите ненужное устройство в боте и запустите проверку снова."}
			}
		}
	}
	if info, ok := report.ParseUserInfo(src.UserInfo); ok && !info.Expire.IsZero() && info.Expire.Before(now) {
		return &Problem{"Подписка закончилась " + day(info.Expire),
			"Поэтому VPN и не подключается. Продлите её в боте или личном кабинете."}
	}
	if src.Format == "" {
		return &Problem{"Подписка не читается", src.Error + ". Пришлите отчёт в поддержку."}
	}
	text := "Панель не выдала ни одного сервера. Пришлите отчёт в поддержку."
	if announce := src.Notices["announce"]; announce != "" {
		text = "Панель передаёт: «" + announce + "». " + text
	}
	return &Problem{"В подписке нет серверов", text}
}

// Card is the subscription as the top of the check screen shows it.
type Card struct {
	Title    string `json:"title"`
	Status   string `json:"status,omitempty"`
	Tone     string `json:"tone,omitempty"`
	Traffic  string `json:"traffic,omitempty"`
	Servers  int    `json:"servers"`
	Profiles int    `json:"profiles"`
}

// The FREE tier keeps every panel account years ahead and holds the real end
// date in our own database; a date this far out says nothing about payment.
const farExpiry = 2 * 365 * 24 * time.Hour

func cardFor(src report.Source, profiles int, now time.Time) *Card {
	card := &Card{Title: src.Title, Servers: src.Servers, Profiles: profiles}
	if card.Title == "" {
		card.Title = "Подписка"
	}
	info, ok := report.ParseUserInfo(src.UserInfo)
	if !ok {
		return card
	}
	card.Traffic = "Трафик " + gigabytes(info.Used)
	if info.Total > 0 {
		card.Traffic += " из " + gigabytes(info.Total)
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

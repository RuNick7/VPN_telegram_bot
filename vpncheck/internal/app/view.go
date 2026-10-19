package app

import (
	"fmt"
	"strings"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/site"
)

// state is everything the page draws, read every half second while it is
// open. Small on purpose: a server's steps and log come one at a time, when
// the customer opens that server (see detail).
type state struct {
	Phase string `json:"phase"`
	// Counts runs, so the page knows a new one from the one it is drawing.
	Run      int          `json:"run"`
	Version  string       `json:"version"`
	Link     string       `json:"link,omitempty"`
	VPN      string       `json:"vpn,omitempty"`
	Problem  *Problem     `json:"problem,omitempty"`
	Card     *Card        `json:"card,omitempty"`
	Progress *progress    `json:"progress,omitempty"`
	Groups   []groupView  `json:"groups,omitempty"`
	Servers  []serverView `json:"servers,omitempty"`
	Summary  *summary     `json:"summary,omitempty"`
	Report   bool         `json:"report"`
	Saved    string       `json:"saved,omitempty"`
	// The report can go to support from here, and where it went once it has.
	CanSend bool       `json:"can_send"`
	Sending bool       `json:"sending,omitempty"`
	Sent    *site.Sent `json:"sent,omitempty"`
	// The page is in the app's window: links go through /api/open.
	Window bool `json:"window,omitempty"`
	// The connection is metered: the page asks before measuring speed.
	Metered bool `json:"metered,omitempty"`
}

type progress struct {
	Done    int    `json:"done"`
	Total   int    `json:"total"`
	Percent int    `json:"percent"`
	Current string `json:"current,omitempty"`
}

// A server or a profile is one of: queued, running, ok, warn, bad.
type serverView struct {
	Host  string  `json:"host"`
	Port  int     `json:"port"`
	Kind  string  `json:"kind"`
	State string  `json:"state"`
	Ping  int64   `json:"ping,omitempty"`
	Mbps  float64 `json:"mbps,omitempty"`
	Note  string  `json:"note,omitempty"`
}

type groupView struct {
	Name    string `json:"name"`
	State   string `json:"state"`
	Ping    int64  `json:"ping,omitempty"`
	Working int    `json:"working"`
	Servers []int  `json:"servers"`
}

type summary struct {
	Works int    `json:"works"`
	Total int    `json:"total"`
	Tone  string `json:"tone"`
	Line  string `json:"line"`
}

// view draws the run as the page shows it. Called under App.mu.
func (r *run) view(s *state) {
	s.Phase, s.Problem, s.Card, s.Link = r.phase, r.problem, r.card, r.link
	if r.vpn != "" {
		s.VPN = r.vpn
	}
	s.Report, s.Saved = r.files != nil, r.saved
	s.Sending, s.Sent = r.sending, r.sent
	if len(r.targets) == 0 {
		return
	}
	s.Servers = make([]serverView, len(r.targets))
	for i, target := range r.targets {
		view := serverView{Host: target.Address, Port: target.Port, Kind: target.Kind(), State: "queued"}
		if i == r.current {
			view.State = "running"
		}
		if result := r.results[i]; result != nil {
			view.State = verdictState(result.Verdict)
			view.Ping = pingMs(result.Best())
			view.Mbps = result.Mbps
			view.Note = r.red.String(note(result))
		}
		s.Servers[i] = view
	}
	for _, g := range r.groups {
		s.Groups = append(s.Groups, groupState(g, s.Servers))
	}

	reached, done := 0, 0
	for i := range r.targets {
		if r.reached[i] {
			reached++
		}
		if r.results[i] != nil {
			done++
		}
	}
	total := len(r.targets)
	if r.active() {
		// The network stages are quick next to the tunnels: a fifth of the bar.
		p := &progress{Done: done, Total: total, Percent: (reached*20 + done*80) / total}
		if r.current >= 0 {
			p.Current = r.targets[r.current].Address
		}
		s.Progress = p
		return
	}
	if r.phase == phaseDone || r.phase == phaseStopped {
		s.Summary = r.summarize(s.Groups, s.Servers)
	}
}

// pingMs rounds up: a reply under a millisecond is still a reply, and 0
// reads as none.
func pingMs(d time.Duration) int64 {
	if d <= 0 {
		return 0
	}
	return max(1, d.Milliseconds())
}

func verdictState(v check.Verdict) string {
	switch v {
	case check.Works:
		return "ok"
	case check.Partial:
		return "warn"
	}
	return "bad"
}

func groupState(g group, servers []serverView) groupView {
	view := groupView{Name: g.name, Servers: g.servers, State: "queued"}
	finished, bad := 0, 0
	for _, i := range g.servers {
		server := servers[i]
		switch server.State {
		case "running":
			view.State = "running"
		case "ok", "warn":
			view.Working++
			if server.Ping > 0 && (view.Ping == 0 || server.Ping < view.Ping) {
				view.Ping = server.Ping
			}
		}
		if server.State == "bad" {
			bad++
		}
		if server.State == "ok" || server.State == "warn" || server.State == "bad" {
			finished++
		}
	}
	if view.State == "running" || finished < len(g.servers) {
		return view
	}
	switch {
	case bad == len(g.servers):
		view.State = "bad"
	case bad == 0 && allOK(g.servers, servers):
		view.State = "ok"
	default:
		view.State = "warn"
	}
	return view
}

func allOK(indices []int, servers []serverView) bool {
	for _, i := range indices {
		if servers[i].State != "ok" {
			return false
		}
	}
	return true
}

// note is a server's result in one line: the first hint, cut to its
// opening clause, or what did not get through it.
func note(result *check.Result) string {
	if result.Verdict == check.Works {
		return ""
	}
	if len(result.Hints) > 0 {
		hint := result.Hints[0]
		// ": " and not ":", which would cut "host:port" in two.
		if i := strings.Index(hint, ": "); i > 0 {
			hint = hint[:i]
		} else if i := strings.Index(hint, ". "); i > 0 {
			hint = hint[:i]
		}
		return strings.TrimSuffix(hint, ".")
	}
	var failed []string
	through := false
	for _, step := range result.Steps {
		through = through || step.Name == check.StepPing
		if through && (step.Status == check.Fail || step.Status == check.Warn) {
			failed = append(failed, step.Name)
		}
	}
	if len(failed) > 0 {
		return "Не прошло: " + strings.Join(failed, ", ")
	}
	return result.Cause
}

// summarize is the headline of the result screen: how many servers work, and
// which profiles a customer would find broken.
func (r *run) summarize(groups []groupView, servers []serverView) *summary {
	sum := &summary{Total: len(servers), Tone: "ok"}
	for _, server := range servers {
		if server.State == "ok" {
			sum.Works++
		}
	}
	if !r.internet {
		sum.Tone, sum.Line = "bad", "Интернет не работает даже без VPN, поэтому серверы проверить нельзя."
		return sum
	}
	var broken, partial []string
	for _, g := range groups {
		switch g.State {
		case "bad":
			broken = append(broken, g.Name)
		case "warn":
			partial = append(partial, g.Name)
		}
	}
	var parts []string
	if len(broken) > 0 {
		parts = append(parts, "Не работают: "+names(broken))
		sum.Tone = "bad"
	}
	if len(partial) > 0 {
		parts = append(parts, "С ошибками: "+names(partial))
		if sum.Tone == "ok" {
			sum.Tone = "warn"
		}
	}
	switch {
	case r.phase == phaseStopped:
		sum.Line = fmt.Sprintf("Проверка остановлена: проверено %d из %d.", countDone(servers), len(servers))
		if len(parts) > 0 {
			sum.Line += " " + strings.Join(parts, ". ") + "."
		}
	case len(parts) == 0:
		sum.Line = "Все серверы работают."
	default:
		sum.Line = strings.Join(parts, ". ") + "."
	}
	return sum
}

func countDone(servers []serverView) int {
	n := 0
	for _, server := range servers {
		if server.State == "ok" || server.State == "warn" || server.State == "bad" {
			n++
		}
	}
	return n
}

func names(list []string) string {
	if len(list) <= 3 {
		return strings.Join(list, ", ")
	}
	return strings.Join(list[:3], ", ") + fmt.Sprintf(" и ещё %d", len(list)-3)
}

// detail is one server opened on the page: every step, the hints, and its
// own Xray log, all through the run's redactor.
type detail struct {
	Host     string     `json:"host"`
	Port     int        `json:"port"`
	Kind     string     `json:"kind"`
	SNI      string     `json:"sni,omitempty"`
	Profiles []string   `json:"profiles"`
	Steps    []stepView `json:"steps"`
	Cause    string     `json:"cause,omitempty"`
	Hints    []string   `json:"hints,omitempty"`
	Exit     string     `json:"exit,omitempty"`
	Log      []string   `json:"log,omitempty"`
}

type stepView struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	Detail string `json:"detail"`
}

// The tail of a server's Xray log is where its failure is; the rest is in
// the saved report.
const detailLogLines = 300

func (r *run) detail(i int) *detail {
	target := r.targets[i]
	d := &detail{Host: target.Address, Port: target.Port, Kind: target.Kind(), SNI: target.SNI, Profiles: target.Profiles}
	result := r.results[i]
	if result == nil {
		return d
	}
	for _, step := range result.Steps {
		status := map[check.Status]string{check.OK: "ok", check.Warn: "warn", check.Fail: "bad", check.Skip: "skip"}[step.Status]
		d.Steps = append(d.Steps, stepView{Name: step.Name, Status: status, Detail: r.red.String(step.Detail)})
	}
	d.Cause = r.red.String(result.Cause)
	for _, hint := range result.Hints {
		d.Hints = append(d.Hints, r.red.String(hint))
	}
	if loc := result.Exit["loc"]; loc != "" {
		d.Exit = loc
		if colo := result.Exit["colo"]; colo != "" {
			d.Exit += ", Cloudflare " + colo
		}
	}
	log := result.Log
	if len(log) > detailLogLines {
		log = log[len(log)-detailLogLines:]
	}
	for _, line := range log {
		d.Log = append(d.Log, r.red.String(line))
	}
	return d
}

// Package report writes what a run found: a summary to read first, one log
// per server, and a single file holding all of it to send to support.
//
// Every byte goes through the run's redactor on the way to disk. The files
// are made to be handed to someone else, so nothing in them may let that
// someone connect as the person who ran the check.
package report

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/nodelog"
	"github.com/RuNick7/vpn-check/internal/redact"
)

// MaxFull keeps the combined report under the 10 MB a support ticket takes
// for one text file, with room to spare.
const MaxFull = 9 << 20

// Source is one subscription the run read.
type Source struct {
	URL      string
	Status   int
	Took     time.Duration
	Format   string
	Title    string
	UserInfo string
	Notices  map[string]string
	Profiles int
	Servers  int
	Error    string
}

type Report struct {
	Started  time.Time
	Finished time.Time
	Version  string
	Xray     string
	Platform string
	Baseline []check.Step
	Sources  []Source
	Results  []*check.Result
	// How many servers there were, of which Results holds the finished ones.
	Total int
	// The run's marker in the nodes' logs, and how this computer's clock
	// compares with real time -- together what finds the run there.
	RunID string
	Clock check.Clock
	// What each node's agent logged for the run, when the operator running
	// it gave vpncheck the agents (see internal/nodes). Empty for customers.
	Nodes []NodeAnswer
}

// New starts the report of a run on this computer.
func New(version string) *Report {
	return &Report{
		Started:  time.Now(),
		Version:  version,
		Xray:     check.XrayVersion(),
		Platform: platform(),
		RunID:    runID(),
	}
}

func platform() string {
	name := map[string]string{"darwin": "macOS", "windows": "Windows", "linux": "Linux"}[runtime.GOOS]
	if name == "" {
		name = runtime.GOOS
	}
	// Not the computer's name: support has no use for it, and it often
	// names a person.
	return name + " " + runtime.GOARCH
}

// runID names one run in the nodes' logs. Random, so it says nothing about
// who ran it; eight hex digits, so two runs do not share one.
func runID() string {
	var raw [4]byte
	_, _ = rand.Read(raw[:])
	return hex.EncodeToString(raw[:])
}

// NodeAnswer is one node agent's reply for the whole run. Its sections line
// up with Results.
type NodeAnswer struct {
	Name     string
	Error    string
	Files    []nodelog.File
	Sections []nodelog.Section
}

type nodeLines struct {
	node string
	nodelog.Section
}

// nodeLinesFor is what the nodes found for one server: every node that has
// lines for it, in the order the agents were given.
func nodeLinesFor(rep *Report, result *check.Result) []nodeLines {
	index := slices.Index(rep.Results, result)
	var found []nodeLines
	for _, node := range rep.Nodes {
		if index >= 0 && index < len(node.Sections) && len(node.Sections[index].Lines) > 0 {
			found = append(found, nodeLines{node.Name, node.Sections[index]})
		}
	}
	return found
}

func describeNode(found nodeLines) string {
	if !found.Attributed {
		return fmt.Sprintf("нода %s: метки нет, ошибки ноды за это время (могут быть и о других клиентах), строк %d", found.node, len(found.Lines))
	}
	return fmt.Sprintf("нода %s: пользователь %s, адрес %s, строк %d", found.node,
		orDash(strings.Join(found.Emails, ", ")), orDash(strings.Join(found.Addresses, ", ")), len(found.Lines))
}

func orDash(s string) string {
	if s == "" {
		return "—"
	}
	return s
}

// Files are the paths written, relative names included for printing.
type Files struct {
	Dir     string
	Summary string
	JSON    string
	Full    string
	Servers []string
}

// Write puts the report into a new directory under root, named by the time
// the run started.
func Write(root string, rep *Report, red *redact.Redactor) (*Files, error) {
	dir := filepath.Join(root, rep.Started.Format("2006-01-02_15-04-05"))
	if err := os.MkdirAll(filepath.Join(dir, "servers"), 0o755); err != nil {
		return nil, err
	}
	files := &Files{
		Dir:     dir,
		Summary: filepath.Join(dir, "summary.txt"),
		JSON:    filepath.Join(dir, "summary.json"),
		Full:    filepath.Join(dir, "report.txt"),
	}

	names := make([]string, len(rep.Results))
	logs := make([]string, len(rep.Results))
	for i, result := range rep.Results {
		names[i] = filepath.Join("servers", serverFile(i, result))
		logs[i] = printable(red.String(serverLog(rep, result, red, nil)))
		path := filepath.Join(dir, names[i])
		if err := os.WriteFile(path, []byte(logs[i]), 0o644); err != nil {
			return nil, err
		}
		files.Servers = append(files.Servers, path)
	}

	summary := printable(red.String(Summary(rep, names)))
	if err := os.WriteFile(files.Summary, []byte(summary), 0o644); err != nil {
		return nil, err
	}
	data, err := summaryJSON(rep, names, red)
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(files.JSON, data, 0o644); err != nil {
		return nil, err
	}
	full := printable(red.String(fullReport(summary, rep, red, MaxFull)))
	if err := os.WriteFile(files.Full, []byte(full), 0o644); err != nil {
		return nil, err
	}
	return files, nil
}

// printable keeps a file something the ticket accepts as text. Xray and the
// servers it talks to can put any byte into an error message, and one stray
// control character would make the site turn the whole report away.
func printable(s string) string {
	return strings.Map(func(r rune) rune {
		if r == 0x7f || (r < 0x20 && r != '\t' && r != '\n' && r != '\r') {
			return -1
		}
		return r
	}, strings.ToValidUTF8(s, "\uFFFD"))
}

var unsafeName = regexp.MustCompile(`[^A-Za-z0-9.-]+`)

func serverFile(index int, result *check.Result) string {
	t := result.Target
	kind := strings.ReplaceAll(t.Kind(), " · ", "-")
	name := fmt.Sprintf("%02d_%s_%d_%s", index+1, t.Address, t.Port, kind)
	return strings.Trim(unsafeName.ReplaceAllString(name, "_"), "_") + ".log"
}

// Summary is the part a person reads: where the check ran from, what the
// subscription held, a line per server, and then each server's stages.
func Summary(rep *Report, logNames []string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Проверка серверов vpncheck %s (Xray %s)\n", rep.Version, rep.Xray)
	fmt.Fprintf(&b, "Начало: %s, длилась %s\n", rep.Started.Format("2006-01-02 15:04:05 -07:00"), duration(rep.Finished.Sub(rep.Started)))
	fmt.Fprintf(&b, "Компьютер: %s\n", rep.Platform)
	switch {
	case rep.Clock.Known:
		fmt.Fprintf(&b, "Часы компьютера: сверены, поправка %+.1f с\n", rep.Clock.Offset.Seconds())
	default:
		b.WriteString("Часы компьютера: не сверены, время на нодах указано по часам компьютера\n")
	}
	if rep.RunID != "" {
		fmt.Fprintf(&b, "Метка проверки в логах нод: vpncheck-%s\n", rep.RunID)
	}

	if len(rep.Baseline) > 0 {
		b.WriteString("\nСоединение без VPN\n")
		for _, step := range rep.Baseline {
			fmt.Fprintf(&b, "  %-10s %s — %s\n", step.Status, step.Name, step.Detail)
		}
	}

	for _, source := range rep.Sources {
		fmt.Fprintf(&b, "\nПодписка %s\n", source.URL)
		if source.Error != "" {
			fmt.Fprintf(&b, "  ОШИБКА: %s\n", source.Error)
			continue
		}
		if source.Status != 0 {
			fmt.Fprintf(&b, "  HTTP %d за %s, ", source.Status, ms(source.Took))
		} else {
			b.WriteString("  ")
		}
		fmt.Fprintf(&b, "формат %s, профилей %d, серверов %d\n", source.Format, source.Profiles, source.Servers)
		if source.Title != "" {
			fmt.Fprintf(&b, "  Название: %s\n", source.Title)
		}
		if info := userInfo(source.UserInfo); info != "" {
			fmt.Fprintf(&b, "  %s\n", info)
		}
		for _, name := range slices.Sorted(maps.Keys(source.Notices)) {
			fmt.Fprintf(&b, "  %s: %s\n", name, source.Notices[name])
		}
	}

	counts := map[check.Verdict]int{}
	for _, result := range rep.Results {
		counts[result.Verdict]++
	}
	fmt.Fprintf(&b, "\nИтог: работает %d из %d", counts[check.Works], rep.Total)
	if counts[check.Partial] > 0 {
		fmt.Fprintf(&b, ", частично %d", counts[check.Partial])
	}
	if counts[check.Broken] > 0 {
		fmt.Fprintf(&b, ", не работает %d", counts[check.Broken])
	}
	if missing := rep.Total - len(rep.Results); missing > 0 {
		fmt.Fprintf(&b, ", не проверено %d (проверку прервали)", missing)
	}
	b.WriteString("\n")
	if len(rep.Nodes) > 0 {
		b.WriteString("\nЛоги нод\n")
		for _, node := range rep.Nodes {
			var unreadable []string
			for _, file := range node.Files {
				if file.Error != "" {
					unreadable = append(unreadable, fmt.Sprintf("%s (%s)", file.Path, file.Error))
				}
			}
			switch {
			case node.Error != "":
				fmt.Fprintf(&b, "  %s: не ответила — %s\n", node.Name, node.Error)
			case len(unreadable) > 0:
				fmt.Fprintf(&b, "  %s: ответила, но не читает: %s\n", node.Name, strings.Join(unreadable, "; "))
			default:
				fmt.Fprintf(&b, "  %s: ответила\n", node.Name)
			}
		}
	}
	b.WriteString("\n")

	if len(rep.Results) > 0 {
		fmt.Fprintf(&b, "%3s  %-34s %-32s %8s  %s\n", "#", "Сервер", "Протокол", "Пинг", "Итог")
		for i, result := range rep.Results {
			ping := "—"
			if best := result.Best(); best > 0 {
				ping = ms(best)
			}
			fmt.Fprintf(&b, "%3d  %-34s %-32s %8s  %s\n", i+1, result.Target.Endpoint(), result.Target.Kind(), ping, result.Verdict)
		}
		b.WriteString("\nПодробно\n")
	}
	for i, result := range rep.Results {
		b.WriteString("\n")
		fmt.Fprintf(&b, "%d. %s — %s — %s\n", i+1, result.Target.Endpoint(), result.Target.Kind(), result.Verdict)
		writeDetails(&b, result, "   ")
		writeNodes(&b, rep, result, "   ")
		if i < len(logNames) {
			fmt.Fprintf(&b, "   Лог: %s\n", filepath.ToSlash(logNames[i]))
		}
	}
	return b.String()
}

func writeDetails(b *strings.Builder, result *check.Result, indent string) {
	t := result.Target
	if len(t.Profiles) > 0 {
		fmt.Fprintf(b, "%sПрофили: %s\n", indent, strings.Join(t.Profiles, ", "))
	}
	if t.SNI != "" || t.Fingerprint != "" || t.Detail != "" {
		var parts []string
		if t.SNI != "" {
			parts = append(parts, "SNI "+t.SNI)
		}
		if t.Fingerprint != "" {
			parts = append(parts, "fingerprint "+t.Fingerprint)
		}
		if t.Detail != "" {
			parts = append(parts, t.Detail)
		}
		fmt.Fprintf(b, "%sНастройки: %s\n", indent, strings.Join(parts, ", "))
	}
	for _, step := range result.Steps {
		fmt.Fprintf(b, "%s%-10s %-18s %s\n", indent, step.Status, step.Name, step.Detail)
	}
	if result.Cause != "" {
		fmt.Fprintf(b, "%sПричина: %s\n", indent, result.Cause)
	}
	if len(result.Hints) > 0 {
		fmt.Fprintf(b, "%sЧто это значит:\n", indent)
		for _, hint := range result.Hints {
			fmt.Fprintf(b, "%s  - %s\n", indent, hint)
		}
	}
}

// writeNodes says, for one server, which nodes logged the run -- the line
// that tells which node behind a shared address actually served it.
func writeNodes(b *strings.Builder, rep *Report, result *check.Result, indent string) {
	if len(rep.Nodes) == 0 {
		return
	}
	found := nodeLinesFor(rep, result)
	if len(found) == 0 {
		fmt.Fprintf(b, "%sНоды: ни на одной нет строк этой проверки\n", indent)
		return
	}
	for _, f := range found {
		fmt.Fprintf(b, "%sНоды: %s\n", indent, describeNode(f))
	}
}

// NodeWindow is when a server's node saw the run, in real time: the tunnel
// stage, by this computer's clock, corrected when the clock could be checked.
// Whole seconds rounded outwards, which is how a node's log is searched.
func NodeWindow(rep *Report, result *check.Result) (from, to time.Time, ok bool) {
	if result.TunnelAt.IsZero() {
		return from, to, false
	}
	from = result.TunnelAt.Add(rep.Clock.Offset).UTC().Truncate(time.Second)
	end := result.TunnelAt.Add(result.TunnelTook + rep.Clock.Offset).UTC()
	if to = end.Truncate(time.Second); to.Before(end) {
		to = to.Add(time.Second)
	}
	return from, to, true
}

// serverLog is one server's file: the summary of it, the outbound it was
// reached with, and Xray's log. keep, when set, limits the log to its last
// lines.
func serverLog(rep *Report, result *check.Result, red *redact.Redactor, keep *int) string {
	var b strings.Builder
	t := result.Target
	fmt.Fprintf(&b, "Сервер: %s — %s — %s\n", t.Endpoint(), t.Kind(), result.Verdict)
	if result.TunnelAt.IsZero() {
		fmt.Fprintf(&b, "Начало: %s, длилась %s\n", result.Started.Format("2006-01-02 15:04:05 -07:00"), duration(result.Took))
	} else {
		// Not Started: the stages before the tunnel run for every server at
		// once, and the tunnels one by one, so a server can wait minutes.
		fmt.Fprintf(&b, "Через сервер: %s, длилось %s\n", result.TunnelAt.Format("2006-01-02 15:04:05 -07:00"), duration(result.TunnelTook))
	}
	if from, to, ok := NodeWindow(rep, result); ok {
		fmt.Fprintf(&b, "Время на ноде (UTC): %s — %s\n", from.Format(time.RFC3339), to.Format(time.RFC3339))
	}
	if result.Marker != "" {
		sent := ""
		if !result.MarkerSent {
			sent = " (не отправлена)"
		}
		fmt.Fprintf(&b, "Метка в логе ноды: %s%s\n", result.Marker, sent)
	}
	writeDetails(&b, result, "")

	b.WriteString("\nНастройки сервера из подписки (секреты скрыты):\n")
	outbounds := []any{red.Config(toAny(t.Outbound))}
	for _, hop := range t.Chain {
		outbounds = append(outbounds, red.Config(toAny(hop)))
	}
	encoded, _ := json.MarshalIndent(outbounds, "", "  ")
	b.Write(encoded)
	b.WriteString("\n")

	lines := result.Log
	if keep != nil && len(lines) > *keep {
		fmt.Fprintf(&b, "\nЛог Xray (последние %d строк из %d, полностью — в папке servers):\n", *keep, len(lines))
		lines = lines[len(lines)-*keep:]
	} else {
		b.WriteString("\nЛог Xray:\n")
	}
	if len(lines) == 0 {
		b.WriteString("(пусто)\n")
	}
	for _, line := range lines {
		b.WriteString(line)
		b.WriteString("\n")
	}
	if len(rep.Nodes) > 0 {
		found := nodeLinesFor(rep, result)
		if len(found) == 0 {
			b.WriteString("\nЛоги нод: ни на одной нет строк этой проверки\n")
		}
		for _, f := range found {
			fmt.Fprintf(&b, "\nЛог ноды — %s:\n", describeNode(f))
			for _, line := range f.Lines {
				b.WriteString(line)
				b.WriteString("\n")
			}
			if f.Truncated {
				b.WriteString("... дальше строки обрезаны\n")
			}
		}
	}
	return b.String()
}

// fullReport is the summary followed by every server's log, cut down to fit
// limit by keeping the end of the longest logs -- where a failure is.
func fullReport(summary string, rep *Report, red *redact.Redactor, limit int) string {
	join := func(keep *int) string {
		var b strings.Builder
		b.WriteString(summary)
		for _, result := range rep.Results {
			b.WriteString("\n" + strings.Repeat("=", 78) + "\n")
			b.WriteString(serverLog(rep, result, red, keep))
		}
		return b.String()
	}
	full := join(nil)
	if len(full) <= limit {
		return full
	}
	longest := 0
	for _, result := range rep.Results {
		longest = max(longest, len(result.Log))
	}
	for keep := longest / 2; keep > 0; keep /= 2 {
		if full = join(&keep); len(full) <= limit {
			return full
		}
	}
	zero := 0
	full = join(&zero)
	if len(full) > limit {
		full = full[:limit]
	}
	return full
}

type jsonStep struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	MS     int64  `json:"ms"`
	Detail string `json:"detail"`
}

type jsonServer struct {
	Endpoint string            `json:"endpoint"`
	Kind     string            `json:"kind"`
	Profiles []string          `json:"profiles"`
	SNI      string            `json:"sni,omitempty"`
	Verdict  string            `json:"verdict"`
	Cause    string            `json:"cause,omitempty"`
	Hints    []string          `json:"hints,omitempty"`
	PingsMS  []int64           `json:"pings_ms,omitempty"`
	Exit     map[string]string `json:"exit,omitempty"`
	Mbps     float64           `json:"mbps,omitempty"`
	Steps    []jsonStep        `json:"steps"`
	Log      string            `json:"log"`
	// When the node saw the run, real time, and what to look for there.
	NodeFrom string `json:"node_from,omitempty"`
	NodeTo   string `json:"node_to,omitempty"`
	Marker   string `json:"marker,omitempty"`
	// What each node's agent logged, on an operator's run.
	Nodes []jsonNode `json:"nodes,omitempty"`
}

type jsonNode struct {
	Node       string   `json:"node"`
	Attributed bool     `json:"attributed"`
	Emails     []string `json:"emails,omitempty"`
	Addresses  []string `json:"addresses,omitempty"`
	Lines      []string `json:"lines"`
}

func summaryJSON(rep *Report, logNames []string, red *redact.Redactor) ([]byte, error) {
	s := red.String
	strs := func(list []string) []string {
		out := make([]string, len(list))
		for i, item := range list {
			out[i] = s(item)
		}
		return out
	}
	steps := func(list []check.Step) []jsonStep {
		out := make([]jsonStep, len(list))
		for i, step := range list {
			out[i] = jsonStep{Name: step.Name, Status: step.Status.String(), MS: step.Took.Milliseconds(), Detail: s(step.Detail)}
		}
		return out
	}
	var servers []jsonServer
	for i, result := range rep.Results {
		server := jsonServer{
			Endpoint: s(result.Target.Endpoint()),
			Kind:     result.Target.Kind(),
			Profiles: strs(result.Target.Profiles),
			SNI:      s(result.Target.SNI),
			Verdict:  result.Verdict.String(),
			Cause:    s(result.Cause),
			Hints:    strs(result.Hints),
			Exit:     result.Exit,
			Mbps:     result.Mbps,
			Steps:    steps(result.Steps),
			Log:      filepath.ToSlash(logNames[i]),
		}
		for _, ping := range result.Pings {
			server.PingsMS = append(server.PingsMS, ping.Milliseconds())
		}
		if from, to, ok := NodeWindow(rep, result); ok {
			server.NodeFrom, server.NodeTo = from.Format(time.RFC3339), to.Format(time.RFC3339)
		}
		if result.MarkerSent {
			server.Marker = result.Marker
		}
		for _, f := range nodeLinesFor(rep, result) {
			server.Nodes = append(server.Nodes, jsonNode{Node: f.node, Attributed: f.Attributed,
				Emails: f.Emails, Addresses: f.Addresses, Lines: strs(f.Lines)})
		}
		servers = append(servers, server)
	}
	var sources []map[string]any
	for _, source := range rep.Sources {
		sources = append(sources, map[string]any{
			"url": s(source.URL), "status": source.Status, "format": source.Format, "title": s(source.Title),
			"profiles": source.Profiles, "servers": source.Servers, "error": s(source.Error),
		})
	}
	return json.MarshalIndent(map[string]any{
		"version":  rep.Version,
		"xray":     rep.Xray,
		"platform": rep.Platform,
		"started":  rep.Started.Format(time.RFC3339),
		"finished": rep.Finished.Format(time.RFC3339),
		"baseline": steps(rep.Baseline),
		"sources":  sources,
		"total":    rep.Total,
		"servers":  servers,
		"run_id":   rep.RunID,
		"clock":    map[string]any{"known": rep.Clock.Known, "offset_ms": rep.Clock.Offset.Milliseconds()},
	}, "", "  ")
}

// OneLine is the summary line a support ticket shows.
func OneLine(rep *Report) string {
	counts := map[check.Verdict]int{}
	var broken []string
	for _, result := range rep.Results {
		counts[result.Verdict]++
		if result.Verdict != check.Works {
			broken = append(broken, result.Target.Endpoint())
		}
	}
	line := fmt.Sprintf("работает %d из %d серверов", counts[check.Works], rep.Total)
	if len(broken) > 0 {
		if len(broken) > 5 {
			broken = append(broken[:5], "…")
		}
		line += "; с ошибками: " + strings.Join(broken, ", ")
	}
	return line
}

// UserInfo is what the panel's subscription-userinfo header says.
type UserInfo struct {
	// Bytes, up and down together; Total 0 means no limit.
	Used, Total int64
	// Zero when the subscription does not expire.
	Expire time.Time
}

// ParseUserInfo reads "upload=1; download=2; total=3; expire=4".
func ParseUserInfo(raw string) (UserInfo, bool) {
	if raw == "" {
		return UserInfo{}, false
	}
	values := map[string]int64{}
	for _, part := range strings.Split(raw, ";") {
		key, value, ok := strings.Cut(strings.TrimSpace(part), "=")
		if !ok {
			continue
		}
		n, err := strconv.ParseInt(strings.TrimSpace(value), 10, 64)
		if err == nil {
			values[key] = n
		}
	}
	info := UserInfo{Used: values["upload"] + values["download"], Total: values["total"]}
	if expire := values["expire"]; expire > 0 {
		info.Expire = time.Unix(expire, 0)
	}
	return info, true
}

func userInfo(raw string) string {
	info, ok := ParseUserInfo(raw)
	if !ok {
		return ""
	}
	parts := []string{"трафик " + gigabytes(info.Used)}
	if info.Total > 0 {
		parts[0] += " из " + gigabytes(info.Total)
	}
	if !info.Expire.IsZero() {
		parts = append(parts, "действует до "+info.Expire.Format("2006-01-02 15:04"))
	}
	return strings.Join(parts, ", ")
}

func gigabytes(n int64) string {
	return fmt.Sprintf("%.2f ГБ", float64(n)/(1<<30))
}

func ms(d time.Duration) string {
	if d < time.Millisecond {
		return "<1 мс"
	}
	return strconv.FormatInt(d.Milliseconds(), 10) + " мс"
}

func duration(d time.Duration) string {
	d = d.Round(time.Second)
	if d < time.Minute {
		return fmt.Sprintf("%d с", int(d.Seconds()))
	}
	return fmt.Sprintf("%d мин %d с", int(d.Minutes()), int(d.Seconds())%60)
}

func toAny(value map[string]any) any {
	var out any
	data, _ := json.Marshal(value)
	_ = json.Unmarshal(data, &out)
	return out
}

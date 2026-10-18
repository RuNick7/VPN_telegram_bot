package report

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
	"unicode/utf8"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/nodelog"
	"github.com/RuNick7/vpn-check/internal/redact"
	"github.com/RuNick7/vpn-check/internal/subscription"
)

const (
	userID   = "b831381d-6324-4d53-ad4f-8cda48b30811"
	shortID  = "6ba85179e30d4fc2"
	subURL   = "https://sub.example.net/api/sub/Xk3pQ9vT2mWz"
	subToken = "Xk3pQ9vT2mWz"
)

func sample(t *testing.T, logLines int) (*Report, *redact.Redactor) {
	t.Helper()
	outbound := map[string]any{
		"tag": "proxy", "protocol": "vless",
		"settings": map[string]any{"address": "de1.example.net", "port": float64(443), "id": userID, "encryption": "none"},
		"streamSettings": map[string]any{"network": "grpc", "security": "reality",
			"realitySettings": map[string]any{"serverName": "www.example.com", "publicKey": "7xhH4b_VkliBxGulljcyPOH-bYUA2dl-XAdZAsfhk04", "shortId": shortID}},
	}
	targets := subscription.Targets([]subscription.Profile{{Name: "Германия", Outbounds: []map[string]any{outbound}}})
	var log []string
	for i := 0; i < logLines; i++ {
		log = append(log, "2026/10/16 10:00:00.000000 [Debug] proxy/vless/outbound: user "+userID+" shortId "+shortID+
			" read tcp 192.168.1.5:50123->203.0.113.5:443 "+strings.Repeat("x", 100))
	}
	result := &check.Result{
		Target:  targets[0],
		Started: time.Now(),
		Steps:   []check.Step{{Name: check.StepPing, Status: check.Fail, Detail: "fetching " + subURL}},
		Verdict: check.Broken,
		Cause:   "invalid user " + userID,
		Log:     log,
	}
	red := redact.New()
	red.AddURL(subURL)
	red.AddConfig(map[string]any{"outbounds": []any{outbound}})
	return &Report{
		Started: time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC), Finished: time.Date(2026, 10, 16, 10, 1, 5, 0, time.UTC),
		Version: "test", Xray: "26.7.28", Platform: "linux/amd64",
		Sources: []Source{{URL: subURL, Status: 200, Format: "Xray JSON", Profiles: 1, Servers: 1,
			UserInfo: "upload=1073741824; download=1073741824; total=10737418240; expire=1793000000"}},
		Results: []*check.Result{result},
		Total:   2,
	}, red
}

func TestWriteLeavesNoSecrets(t *testing.T) {
	rep, red := sample(t, 20)
	files, err := Write(t.TempDir(), rep, red)
	if err != nil {
		t.Fatal(err)
	}
	paths := append([]string{files.Summary, files.JSON, files.Full}, files.Servers...)
	for _, path := range paths {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		text := string(data)
		for _, secret := range []string{userID, shortID, subToken, "7xhH4b_Vkli", "192.168.1.5"} {
			if strings.Contains(text, secret) {
				t.Errorf("%s holds %s", filepath.Base(path), secret)
			}
		}
	}
	summary, _ := os.ReadFile(files.Summary)
	for _, want := range []string{"de1.example.net:443", "vless · grpc · reality", "НЕ РАБОТАЕТ", "не проверено 1",
		"трафик 2.00 ГБ из 10.00 ГБ", "[ссылка подписки]", "servers/01_de1.example.net_443_vless-grpc-reality.log"} {
		if !strings.Contains(string(summary), want) {
			t.Errorf("summary lacks %q:\n%s", want, summary)
		}
	}
}

func TestWriteKeepsFilesPlainText(t *testing.T) {
	rep, red := sample(t, 1)
	rep.Results[0].Log = append(rep.Results[0].Log, "reply \x00\x07\x1b[31m\xff\xfe end\tok\r")
	files, err := Write(t.TempDir(), rep, red)
	if err != nil {
		t.Fatal(err)
	}
	for _, path := range append([]string{files.Summary, files.Full}, files.Servers...) {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if !utf8.Valid(data) {
			t.Errorf("%s is not UTF-8", filepath.Base(path))
		}
		for _, c := range data {
			if c == 0x7f || (c < 0x20 && c != '\t' && c != '\n' && c != '\r') {
				t.Errorf("%s holds control byte %#x", filepath.Base(path), c)
				break
			}
		}
	}
	full, _ := os.ReadFile(files.Full)
	if !strings.Contains(string(full), "reply [31m\uFFFD end\tok") {
		t.Errorf("log line mangled:\n%s", full)
	}
}

func TestFullReportFitsTheLimit(t *testing.T) {
	rep, red := sample(t, 5000)
	summary := Summary(rep, []string{"servers/01.log"})
	full := fullReport(summary, rep, red, 64<<10)
	if len(full) > 64<<10 {
		t.Fatalf("%d bytes", len(full))
	}
	if !strings.Contains(full, "последние") || !strings.Contains(full, "Причина") {
		t.Fatal("trimmed report lost its summary or its note")
	}
}

func TestOneLine(t *testing.T) {
	rep, _ := sample(t, 0)
	if got := OneLine(rep); got != "работает 0 из 2 серверов; с ошибками: de1.example.net:443" {
		t.Fatal(got)
	}
}

// What admin_bot reads to ask the nodes: the window each server's node saw
// the run in, real time, and its marker. Its parser pins these lines too.
func TestNodeWindowAndMarker(t *testing.T) {
	rep, red := sample(t, 1)
	rep.RunID = "0a1b2c3d"
	rep.Clock = check.Clock{Offset: -2500 * time.Millisecond, Known: true}
	result := rep.Results[0]
	result.TunnelAt = time.Date(2026, 10, 16, 23, 0, 3, 400_000_000, time.FixedZone("MSK", 3*3600))
	result.TunnelTook = 4 * time.Second
	result.Marker, result.MarkerSent = check.Marker(rep.RunID, 1), true

	from, to, ok := NodeWindow(rep, result)
	if !ok || !from.Equal(time.Date(2026, 10, 16, 20, 0, 0, 0, time.UTC)) || !to.Equal(time.Date(2026, 10, 16, 20, 0, 5, 0, time.UTC)) {
		t.Fatalf("%v %v %v", from, to, ok)
	}
	files, err := Write(t.TempDir(), rep, red)
	if err != nil {
		t.Fatal(err)
	}
	full, _ := os.ReadFile(files.Full)
	for _, want := range []string{
		"Часы компьютера: сверены, поправка -2.5 с\n",
		"Метка проверки в логах нод: vpncheck-0a1b2c3d\n",
		"\nСервер: de1.example.net:443 — vless · grpc · reality — НЕ РАБОТАЕТ\nЧерез сервер: 2026-10-16 23:00:03 +03:00, длилось 4 с\n",
		"\nВремя на ноде (UTC): 2026-10-16T20:00:00Z — 2026-10-16T20:00:05Z\n",
		"\nМетка в логе ноды: vpncheck-0a1b2c3d-01.invalid\n",
	} {
		if !strings.Contains(string(full), want) {
			t.Errorf("report lacks %q", want)
		}
	}

	rep.Clock = check.Clock{}
	result.MarkerSent = false
	summary := Summary(rep, nil)
	if !strings.Contains(summary, "Часы компьютера: не сверены") {
		t.Error(summary)
	}
	if log := serverLog(rep, result, red, nil); !strings.Contains(log, "vpncheck-0a1b2c3d-01.invalid (не отправлена)") {
		t.Error(log)
	}
}

// An operator's run: each node's lines under the server they belong to.
func TestNodeLinesSitWithTheirServer(t *testing.T) {
	rep, red := sample(t, 1)
	second := *rep.Results[0]
	second.Target = &subscription.Target{Address: "nl1.example.net", Port: 8443, Protocol: "vless"}
	rep.Results = append(rep.Results, &second)
	line := "2026/10/16 20:00:03.000000 from 198.51.100.7:50002 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80 [in >> out] email: u-ops"
	rep.Nodes = []NodeAnswer{
		{Name: "de1", Files: []nodelog.File{{Path: "/var/log/remnanode/access.log"}}, Sections: []nodelog.Section{
			{Attributed: true, Emails: []string{"u-ops"}, Addresses: []string{"198.51.100.7"}, Lines: []string{line}},
			{},
		}},
		{Name: "nl1", Files: []nodelog.File{{Path: "/var/log/remnanode/error.log", Error: "permission denied"}}, Sections: []nodelog.Section{
			{}, {Lines: []string{"2026/10/16 20:00:04.000000 [Warning] something"}, Truncated: true},
		}},
		{Name: "fi1", Error: "HTTP 401: unauthorized"},
	}
	files, err := Write(t.TempDir(), rep, red)
	if err != nil {
		t.Fatal(err)
	}
	summary, _ := os.ReadFile(files.Summary)
	for _, want := range []string{
		"\nЛоги нод\n  de1: ответила\n  nl1: ответила, но не читает: /var/log/remnanode/error.log (permission denied)\n  fi1: не ответила — HTTP 401: unauthorized\n",
		"   Ноды: нода de1: пользователь u-ops, адрес 198.51.100.7, строк 1\n",
		"   Ноды: нода nl1: метки нет, ошибки ноды за это время (могут быть и о других клиентах), строк 1\n",
	} {
		if !strings.Contains(string(summary), want) {
			t.Errorf("summary lacks %q:\n%s", want, summary)
		}
	}
	first, _ := os.ReadFile(files.Servers[0])
	if !strings.Contains(string(first), "\nЛог ноды — нода de1: пользователь u-ops, адрес 198.51.100.7, строк 1:\n"+line+"\n") ||
		strings.Contains(string(first), "нода nl1") {
		t.Errorf("first server:\n%s", first)
	}
	secondLog, _ := os.ReadFile(files.Servers[1])
	if !strings.Contains(string(secondLog), "... дальше строки обрезаны") {
		t.Errorf("second server:\n%s", secondLog)
	}

	var parsed struct {
		Servers []struct {
			Nodes []struct {
				Node       string   `json:"node"`
				Attributed bool     `json:"attributed"`
				Lines      []string `json:"lines"`
			} `json:"nodes"`
		} `json:"servers"`
	}
	data, _ := os.ReadFile(files.JSON)
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatal(err)
	}
	if len(parsed.Servers) != 2 || len(parsed.Servers[0].Nodes) != 1 || parsed.Servers[0].Nodes[0].Node != "de1" ||
		!parsed.Servers[0].Nodes[0].Attributed || parsed.Servers[1].Nodes[0].Node != "nl1" {
		t.Fatalf("%s", data)
	}

	rep.Nodes[0].Sections, rep.Nodes[1].Sections = nil, nil
	if log := serverLog(rep, rep.Results[0], red, nil); !strings.Contains(log, "\nЛоги нод: ни на одной нет строк этой проверки\n") {
		t.Error(log)
	}
	rep.Nodes = nil
	if log := serverLog(rep, rep.Results[0], red, nil); strings.Contains(log, "нод:") || strings.Contains(Summary(rep, nil), "Логи нод") {
		t.Error("a customer's report mentions nodes")
	}
}

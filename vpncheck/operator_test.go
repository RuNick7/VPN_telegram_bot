package main

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/nodelog"
	"github.com/RuNick7/vpn-check/internal/nodes"
	"github.com/RuNick7/vpn-check/internal/report"
	"github.com/RuNick7/vpn-check/internal/subscription"
)

const (
	agentToken = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
	botToken   = "123456:secret-bot-token"
)

func writeFile(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), ".env")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestReadEnv(t *testing.T) {
	values, err := readEnv(writeFile(t, "# comment\n\nA=1\nexport B = two \nC=\"quoted # not a comment\"\n"+
		"D='single'\nE=value # trailing comment\nnot a pair\nF=\n"))
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]string{"A": "1", "B": "two", "C": "quoted # not a comment", "D": "single", "E": "value", "F": ""}
	if len(values) != len(want) {
		t.Fatalf("%v", values)
	}
	for key, value := range want {
		if values[key] != value {
			t.Errorf("%s = %q, want %q", key, values[key], value)
		}
	}
	if _, err := readEnv(filepath.Join(t.TempDir(), "missing")); err == nil {
		t.Error("a missing file read fine")
	}
}

func TestLoadOperator(t *testing.T) {
	fp := strings.Repeat("ab", 32)
	fromEnv := "de1=https://" + agentToken + "@de1.example.net:7443#" + fp
	fromFlag := "nl1=https://" + agentToken + "@nl1.example.net:7443#" + fp
	t.Setenv("NODE_LOG_AGENTS", "")
	t.Setenv("ADMIN_BOT_TOKEN", "from-environment")
	t.Setenv("ADMIN_IDS", "999")

	env := writeFile(t, "NODE_LOG_AGENTS="+fromEnv+"\nADMIN_BOT_TOKEN="+botToken+"\nADMIN_IDS=11, 22,x\n")
	op, err := loadOperator("", env)
	if err != nil {
		t.Fatal(err)
	}
	if len(op.agents) != 1 || op.agents[0].Name != "de1" || op.token != botToken || len(op.chats) != 2 || op.chats[1] != 22 {
		t.Fatalf("%+v", op)
	}

	// -agents wins over the file; what the file lacks comes from the environment.
	op, err = loadOperator(fromFlag, writeFile(t, "NODE_LOG_AGENTS="+fromEnv+"\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(op.agents) != 1 || op.agents[0].Name != "nl1" || op.token != "from-environment" || len(op.chats) != 1 || op.chats[0] != 999 {
		t.Fatalf("%+v", op)
	}

	// A customer's run: nothing set, nothing asked.
	t.Setenv("ADMIN_BOT_TOKEN", "")
	t.Setenv("ADMIN_IDS", "")
	if op, err = loadOperator("", ""); err != nil || len(op.agents) != 0 || op.token != "" || len(op.chats) != 0 {
		t.Fatalf("%+v %v", op, err)
	}

	_, err = loadOperator("de1=https://"+agentToken+"@x:1", "")
	if err == nil || strings.Contains(err.Error(), agentToken) {
		t.Fatalf("bad agent: %v", err)
	}
	if _, err := loadOperator("", filepath.Join(t.TempDir(), "missing")); err == nil {
		t.Error("a missing -env file was accepted")
	}
}

func TestPruneTouchesOnlyOldRuns(t *testing.T) {
	root := t.TempDir()
	now := time.Date(2026, 10, 16, 12, 0, 0, 0, time.Local)
	for _, name := range []string{"2026-09-01_08-00-00", "2026-10-15_08-00-00", "notes", "2020-01-01"} {
		if err := os.MkdirAll(filepath.Join(root, name, "servers"), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(root, "2026-01-01_00-00-00"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	removed, err := prune(root, 30, now)
	if err != nil || removed != 1 {
		t.Fatalf("%d %v", removed, err)
	}
	entries, _ := os.ReadDir(root)
	var left []string
	for _, entry := range entries {
		left = append(left, entry.Name())
	}
	if strings.Join(left, " ") != "2020-01-01 2026-01-01_00-00-00 2026-10-15_08-00-00 notes" {
		t.Fatal(left)
	}
}

func TestNotifySendsTheReportToEveryChat(t *testing.T) {
	var mu sync.Mutex
	var chats, captions, files []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/bot"+botToken+"/sendDocument" {
			http.NotFound(w, r)
			return
		}
		file, header, err := r.FormFile("document")
		if err != nil {
			t.Error(err)
			return
		}
		data, _ := io.ReadAll(file)
		chat := r.FormValue("chat_id")
		mu.Lock()
		chats, captions, files = append(chats, chat), append(captions, r.FormValue("caption")), append(files, header.Filename+":"+string(data))
		mu.Unlock()
		if chat == "22" {
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "description": "Bad Request: chat not found"})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}))
	defer server.Close()
	defer func(old string) { telegramAPI = old }(telegramAPI)
	telegramAPI = server.URL

	path := filepath.Join(t.TempDir(), "report.txt")
	if err := os.WriteFile(path, []byte("отчёт"), 0o644); err != nil {
		t.Fatal(err)
	}
	op := &operator{token: botToken, chats: []int64{11, 22}}
	errs := notify(context.Background(), op, strings.Repeat("я", 1500), path)
	if len(errs) != 1 || !strings.Contains(errs[0].Error(), "чат 22") || !strings.Contains(errs[0].Error(), "chat not found") {
		t.Fatalf("%v", errs)
	}
	if strings.Join(chats, ",") != "11,22" || files[0] != "report.txt:отчёт" || len([]rune(captions[0])) != 1001 {
		t.Fatalf("%v %v %d", chats, files, len([]rune(captions[0])))
	}

	// An unreachable API names the URL, and with it the token: it is scrubbed.
	telegramAPI = "http://127.0.0.1:9"
	errs = notify(context.Background(), op, "итог", path)
	if len(errs) != 2 {
		t.Fatalf("%v", errs)
	}
	for _, err := range errs {
		if strings.Contains(err.Error(), botToken) || strings.Contains(err.Error(), "secret-bot-token") {
			t.Errorf("token in %q", err)
		}
	}
}

func TestNotifyCaption(t *testing.T) {
	rep := &report.Report{Total: 1, Results: []*check.Result{{Target: &subscription.Target{Address: "de1.example.net", Port: 443}, Verdict: check.Works}}}
	if got := notifyCaption(rep); got != "Проверка серверов: работает 1 из 1 серверов" {
		t.Fatal(got)
	}
	rep.Nodes = []report.NodeAnswer{{Name: "de1"}, {Name: "nl1", Error: "timeout"}}
	if got := notifyCaption(rep); !strings.HasSuffix(got, "\nЛоги нод не получены: nl1") {
		t.Fatal(got)
	}
}

// fakeAgent answers like vpncheck-agent: a section per window, in order.
func fakeAgent(t *testing.T, name string, queries *[]nodelog.Query) nodes.Agent {
	t.Helper()
	var mu sync.Mutex
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var query nodelog.Query
		if err := json.NewDecoder(r.Body).Decode(&query); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		mu.Lock()
		*queries = append(*queries, query)
		mu.Unlock()
		response := nodelog.Response{Node: name, Files: []nodelog.File{{Path: "/var/log/remnanode/access.log", Size: 1}}}
		for _, window := range query.Windows {
			section := nodelog.Section{Window: window}
			if window.Marker != "" {
				section.Attributed, section.Lines = true, []string{name + " saw " + window.Server}
			}
			response.Sections = append(response.Sections, section)
		}
		_ = json.NewEncoder(w).Encode(response)
	}))
	t.Cleanup(server.Close)
	sum := sha256.Sum256(server.Certificate().Raw)
	return nodes.Agent{Name: name, URL: server.URL, Token: agentToken, Fingerprint: sum[:]}
}

func TestAskNodesKeepsSectionsInLineWithServers(t *testing.T) {
	var queries []nodelog.Query
	agent := fakeAgent(t, "de1", &queries)
	down := nodes.Agent{Name: "down", URL: "https://127.0.0.1:9", Token: agentToken, Fingerprint: agent.Fingerprint}

	start := time.Date(2026, 10, 16, 20, 0, 0, 0, time.UTC)
	rep := &report.Report{RunID: "0a1b2c3d", Clock: check.Clock{Known: true}}
	total := nodeQueryBatch + 3
	for i := range total {
		result := &check.Result{
			Target:  &subscription.Target{Address: "de1.example.net", Port: 1000 + i},
			Started: start, Took: 3 * time.Second, Verdict: check.Works,
			Marker: check.Marker(rep.RunID, i+1), MarkerSent: i != 1,
		}
		if i != 2 {
			result.TunnelAt, result.TunnelTook = start.Add(time.Second), time.Second
		}
		if i == 3 {
			result.Verdict = check.Broken
		}
		rep.Results = append(rep.Results, result)
	}
	rep.Total = total

	answers := askNodes(context.Background(), rep, []nodes.Agent{agent, down})
	if len(queries) != 2 || len(queries[0].Windows) != nodeQueryBatch || len(queries[1].Windows) != 3 || queries[0].SlackSeconds != 5 {
		t.Fatalf("%d queries", len(queries))
	}
	w := queries[0].Windows
	if w[0].Marker != check.Marker("0a1b2c3d", 1) || w[1].Marker != "" || !w[0].From.Equal(start.Add(time.Second)) ||
		!w[2].To.Equal(start.Add(3*time.Second)) || w[2].Server != "de1.example.net:1002" || !w[3].Failed || w[0].Failed {
		t.Fatalf("%+v", w[:4])
	}

	if answers[0].Error != "" || len(answers[0].Sections) != total || answers[0].Sections[total-1].Lines[0] != "de1 saw de1.example.net:"+strconv.Itoa(1000+total-1) {
		t.Fatalf("%+v", answers[0])
	}
	if answers[1].Name != "down" || answers[1].Error == "" || answers[1].Sections != nil {
		t.Fatalf("%+v", answers[1])
	}

	// An agent that answers for fewer servers than asked is not trusted to line up.
	short := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(nodelog.Response{Node: "short", Sections: []nodelog.Section{{Lines: []string{"x"}}}})
	}))
	defer short.Close()
	sum := sha256.Sum256(short.Certificate().Raw)
	answers = askNodes(context.Background(), rep, []nodes.Agent{{Name: "short", URL: short.URL, Token: agentToken, Fingerprint: sum[:]}})
	if answers[0].Error == "" || answers[0].Sections != nil {
		t.Fatalf("%+v", answers[0])
	}

	rep.Clock.Known = false
	queries = nil
	askNodes(context.Background(), rep, []nodes.Agent{agent})
	if queries[0].SlackSeconds != 120 {
		t.Fatalf("%+v", queries[0].SlackSeconds)
	}
}

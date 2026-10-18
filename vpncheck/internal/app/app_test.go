package app

import (
	"archive/zip"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	xlog "github.com/xtls/xray-core/common/log"
	"github.com/xtls/xray-core/core"
	"github.com/xtls/xray-core/infra/conf/serial"

	"github.com/RuNick7/vpn-check/internal/check"
)

// These run the whole app the way the page drives it, against a real Xray
// server on loopback and a subscription served from here.

func TestMain(m *testing.M) {
	check.ServeWorker()
	xlog.RegisterHandler(quietLog{})
	os.Exit(m.Run())
}

type quietLog struct{}

func (quietLog) Handle(xlog.Message) {}

const testUUID = "b831381d-6324-4d53-ad4f-8cda48b30811"
const testToken = "test-token"

// internet stands in for what lies behind a server.
func internet(t *testing.T) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/generate_204":
			w.WriteHeader(http.StatusNoContent)
		case "/cdn-cgi/trace":
			fmt.Fprint(w, "fl=1\nip=203.0.113.7\nloc=NL\ncolo=AMS\nwarp=off\nts=1700000000.000\n")
		case "/down":
			w.Write(bytes.Repeat([]byte{'x'}, 64<<10))
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(server.Close)
	return server
}

func freePort(t *testing.T) int {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	return listener.Addr().(*net.TCPAddr).Port
}

// vlessNode runs a VLESS server the way a node does, and returns its port.
func vlessNode(t *testing.T) int {
	t.Helper()
	port := freePort(t)
	data, _ := json.Marshal(map[string]any{
		"log": map[string]any{"loglevel": "none", "access": "none"},
		"inbounds": []any{map[string]any{
			"listen": "127.0.0.1", "port": port, "protocol": "vless",
			"settings": map[string]any{"clients": []any{map[string]any{"id": testUUID}}, "decryption": "none"},
		}},
		"outbounds": []any{map[string]any{"protocol": "freedom", "settings": map[string]any{
			"finalRules": []any{map[string]any{"action": "allow"}},
		}}},
	})
	config, err := serial.LoadJSONConfig(bytes.NewReader(data))
	if err != nil {
		t.Fatal(err)
	}
	instance, err := core.New(config)
	if err != nil {
		t.Fatal(err)
	}
	if err := instance.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { instance.Close() })
	return port
}

func vlessOutbound(tag string, port int) map[string]any {
	return map[string]any{
		"tag": tag, "protocol": "vless",
		"settings": map[string]any{"vnext": []any{map[string]any{
			"address": "127.0.0.1", "port": port,
			"users": []any{map[string]any{"id": testUUID, "encryption": "none"}},
		}}},
		"streamSettings": map[string]any{"network": "tcp", "security": "none"},
	}
}

// panel serves one subscription the way Remnawave does for Happ: Xray JSON,
// one config per profile, with the title and traffic in headers.
type panel struct {
	*httptest.Server
	mu      sync.Mutex
	status  int
	body    []byte
	headers map[string]string
}

func newPanel(t *testing.T, profiles map[string][]map[string]any, order []string) *panel {
	t.Helper()
	var configs []any
	for _, name := range order {
		outbounds := []any{}
		for _, outbound := range profiles[name] {
			outbounds = append(outbounds, outbound)
		}
		outbounds = append(outbounds, map[string]any{"tag": "direct", "protocol": "freedom"})
		configs = append(configs, map[string]any{"remarks": name, "outbounds": outbounds})
	}
	body, _ := json.Marshal(configs)
	p := &panel{status: http.StatusOK, body: body, headers: map[string]string{
		"profile-title":         "base64:" + base64.StdEncoding.EncodeToString([]byte("KairaVPN")),
		"subscription-userinfo": fmt.Sprintf("upload=0; download=%d; total=0; expire=%d", 3<<30, time.Now().Add(20*24*time.Hour).Unix()),
	}}
	p.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p.mu.Lock()
		defer p.mu.Unlock()
		for name, value := range p.headers {
			w.Header().Set(name, value)
		}
		w.WriteHeader(p.status)
		w.Write(p.body)
	}))
	t.Cleanup(p.Close)
	return p
}

func (p *panel) link() string { return p.URL + "/SayZcYcdx7zRHfxe" }

type fakeDesktop struct {
	mu       sync.Mutex
	copied   string
	revealed string
	opened   string
	text     string
}

func (f *fakeDesktop) Open(url string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.opened = url
	return nil
}

func (f *fakeDesktop) CopyFile(path string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.copied = path
	return nil
}

func (f *fakeDesktop) ReadText() (string, error) { return f.text, nil }

func (f *fakeDesktop) Reveal(path string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.revealed = path
	return nil
}

type harness struct {
	t    *testing.T
	app  *App
	desk *fakeDesktop
	srv  *httptest.Server
	cfg  Config
}

func newHarness(t *testing.T, web string) *harness {
	t.Helper()
	root := t.TempDir()
	cfg := Config{
		Version:   "test",
		Dir:       filepath.Join(root, "reports"),
		Downloads: filepath.Join(root, "Downloads"),
		LinkFile:  filepath.Join(root, "config", "subscription"),
		UserAgent: "Happ/test",
		Options: check.Options{
			Timeout:    3 * time.Second,
			Pings:      2,
			PingURL:    web + "/generate_204",
			TraceURL:   web + "/cdn-cgi/trace",
			Probes:     []check.Probe{{Name: "Сайт", URL: web + "/generate_204", Want: http.StatusNoContent}},
			SpeedBytes: 1,
			SpeedURL:   web + "/down?bytes=%d",
			Parallel:   4,
		},
	}
	h := &harness{t: t, app: New(cfg, testToken), desk: &fakeDesktop{}, cfg: cfg}
	h.app.desk = h.desk
	h.srv = httptest.NewServer(h.app.Handler())
	t.Cleanup(h.srv.Close)
	return h
}

func (h *harness) call(method, path string, body any, into any) int {
	h.t.Helper()
	var reader io.Reader
	if body != nil {
		data, _ := json.Marshal(body)
		reader = bytes.NewReader(data)
	}
	req, _ := http.NewRequest(method, h.srv.URL+path, reader)
	req.Header.Set("Authorization", "Bearer "+testToken)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		h.t.Fatal(err)
	}
	defer resp.Body.Close()
	if into != nil {
		if err := json.NewDecoder(resp.Body).Decode(into); err != nil {
			h.t.Fatalf("%s %s: %v", method, path, err)
		}
	}
	return resp.StatusCode
}

// wait polls the state the way the page does until the run is over.
func (h *harness) wait() state {
	h.t.Helper()
	deadline := time.Now().Add(90 * time.Second)
	for time.Now().Before(deadline) {
		var s state
		h.call("GET", "/api/state", nil, &s)
		if s.Phase != phaseFetching && s.Phase != phaseNetwork && s.Phase != phaseTunnels {
			return s
		}
		time.Sleep(200 * time.Millisecond)
	}
	h.t.Fatal("the run did not finish")
	return state{}
}

func TestCheckFromLinkToCopiedReport(t *testing.T) {
	web := internet(t)
	good := vlessOutbound("proxy", vlessNode(t))
	dead := vlessOutbound("proxy2", freePort(t))
	p := newPanel(t, map[string][]map[string]any{
		"🇳🇱 Нидерланды": {good, dead},
		"🇩🇪 Германия":   {good},
		"🇫🇮 Финляндия":  {dead},
	}, []string{"🇳🇱 Нидерланды", "🇩🇪 Германия", "🇫🇮 Финляндия"})
	h := newHarness(t, web.URL)

	var started state
	if status := h.call("POST", "/api/check", map[string]string{"link": "  " + p.link() + "\n"}, &started); status != http.StatusOK {
		t.Fatalf("check: %d", status)
	}
	s := h.wait()
	if s.Phase != phaseDone {
		t.Fatalf("phase %q, problem %+v", s.Phase, s.Problem)
	}
	if s.Card == nil || s.Card.Title != "KairaVPN" || !strings.HasPrefix(s.Card.Status, "Активна до ") || s.Card.Traffic != "Трафик 3,0 ГБ" {
		t.Errorf("card %+v", s.Card)
	}
	if s.Card.Servers != 2 || s.Card.Profiles != 3 {
		t.Errorf("card counts %+v", s.Card)
	}
	var states []string
	for _, g := range s.Groups {
		states = append(states, g.Name+"="+g.State)
	}
	if got := strings.Join(states, " "); got != "🇳🇱 Нидерланды=warn 🇩🇪 Германия=ok 🇫🇮 Финляндия=bad" {
		t.Errorf("groups %s", got)
	}
	if s.Summary == nil || s.Summary.Works != 1 || s.Summary.Total != 2 || s.Summary.Tone != "bad" {
		t.Fatalf("summary %+v", s.Summary)
	}
	if s.Summary.Line != "Не работают: 🇫🇮 Финляндия. С ошибками: 🇳🇱 Нидерланды." {
		t.Errorf("line %q", s.Summary.Line)
	}
	if !s.Report || s.Servers[1].Note == "" || s.Servers[0].Ping <= 0 {
		t.Errorf("servers %+v, report %v", s.Servers, s.Report)
	}

	var d detail
	if status := h.call("GET", "/api/server/1", nil, &d); status != http.StatusOK || len(d.Steps) == 0 || d.Cause == "" {
		t.Errorf("detail %d %+v", status, d)
	}
	raw, _ := json.Marshal(d)
	if strings.Contains(string(raw), testUUID) {
		t.Error("the user's UUID reached the page")
	}

	var saved struct{ Path string }
	if status := h.call("POST", "/api/save", map[string]any{}, &saved); status != http.StatusOK {
		t.Fatalf("save: %d", status)
	}
	if filepath.Dir(saved.Path) != h.cfg.Downloads || h.desk.revealed != saved.Path {
		t.Errorf("saved to %q, revealed %q", saved.Path, h.desk.revealed)
	}
	report := readZip(t, saved.Path, "report.txt")
	if !strings.Contains(report, "работает 1 из 2") && !strings.Contains(report, "Итог: работает 1 из 2") {
		t.Errorf("report.txt:\n%s", report)
	}
	for _, secret := range []string{testUUID, "SayZcYcdx7zRHfxe"} {
		if strings.Contains(report, secret) {
			t.Errorf("report.txt holds %s", secret)
		}
	}
	// A second save keeps the first.
	var again struct{ Path string }
	h.call("POST", "/api/save", map[string]any{}, &again)
	if again.Path == saved.Path || !strings.HasSuffix(again.Path, " (2).zip") {
		t.Errorf("second save %q", again.Path)
	}

	var copied struct{ Name string }
	if status := h.call("POST", "/api/copy", map[string]any{}, &copied); status != http.StatusOK {
		t.Fatalf("copy: %d", status)
	}
	if h.desk.copied == "" || filepath.Base(h.desk.copied) != copied.Name || !strings.HasPrefix(copied.Name, "vpncheck-") {
		t.Errorf("copied %q as %q", h.desk.copied, copied.Name)
	}

	if got := readLink(h.cfg.LinkFile); got != p.link() {
		t.Errorf("remembered %q", got)
	}
	// Windows keeps only a read-only bit; the profile's ACL is what guards it there.
	if info, err := os.Stat(h.cfg.LinkFile); err != nil || runtime.GOOS != "windows" && info.Mode().Perm() != 0o600 {
		t.Errorf("link file %v %v", info, err)
	}
}

func readZip(t *testing.T, path, name string) string {
	t.Helper()
	zr, err := zip.OpenReader(path)
	if err != nil {
		t.Fatal(err)
	}
	defer zr.Close()
	for _, file := range zr.File {
		if file.Name == name {
			in, _ := file.Open()
			data, _ := io.ReadAll(in)
			in.Close()
			return string(data)
		}
	}
	t.Fatalf("%s not in %s", name, path)
	return ""
}

func TestSubscriptionProblems(t *testing.T) {
	web := internet(t)
	past := time.Now().Add(-72 * time.Hour)
	cases := []struct {
		name    string
		status  int
		body    string
		headers map[string]string
		want    string
	}{
		{"unknown link", http.StatusNotFound, "Not Found", nil, "Подписка не найдена"},
		{"panel error", http.StatusBadGateway, "", nil, "Сервер подписок ответил ошибкой"},
		{"device limit", http.StatusOK, "", map[string]string{"x-hwid-max-devices-reached": "true"}, "Все места для устройств заняты"},
		{"expired", http.StatusOK, "", map[string]string{"subscription-userinfo": fmt.Sprintf("upload=0; download=0; total=0; expire=%d", past.Unix())}, "Подписка закончилась " + day(past)},
		{"no servers", http.StatusOK, "", nil, "В подписке нет серверов"},
		{"not a subscription", http.StatusOK, "<html>hello</html>", nil, "Подписка не читается"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			p := newPanel(t, nil, nil)
			p.status, p.body, p.headers = c.status, []byte(c.body), c.headers
			h := newHarness(t, web.URL)
			h.call("POST", "/api/check", map[string]string{"link": p.link()}, nil)
			s := h.wait()
			if s.Phase != phaseFailed || s.Problem == nil || s.Problem.Title != c.want {
				t.Fatalf("phase %q, problem %+v", s.Phase, s.Problem)
			}
			// Even then there is a report to send: it shows what the panel said.
			if !s.Report {
				t.Error("no report")
			}
			if readLink(h.cfg.LinkFile) != "" {
				t.Error("a link that gave nothing was remembered")
			}
		})
	}
}

func TestLinkProblemsComeBackBeforeAnyRun(t *testing.T) {
	h := newHarness(t, "http://127.0.0.1:1")
	h.app.cfg.Domains = []string{"sub.example.com"}
	var out struct{ Problem *Problem }
	if status := h.call("POST", "/api/check", map[string]string{"link": "https://evil.example.net/SayZcYcdx7zRHfxe"}, &out); status != http.StatusUnprocessableEntity {
		t.Fatalf("status %d", status)
	}
	if out.Problem == nil || out.Problem.Title != "Это ссылка не на нашу подписку" {
		t.Fatalf("problem %+v", out.Problem)
	}
	var s state
	h.call("GET", "/api/state", nil, &s)
	if s.Phase != phaseIdle {
		t.Fatalf("a run started: %q", s.Phase)
	}
}

func TestPasteGivesOnlyALink(t *testing.T) {
	h := newHarness(t, "http://127.0.0.1:1")
	var out struct {
		Link    string
		Problem *Problem
	}
	h.desk.text = "Ваша ссылка: https://sub.example.com/SayZcYcdx7zRHfxe\n"
	h.call("GET", "/api/paste", nil, &out)
	if out.Link != "https://sub.example.com/SayZcYcdx7zRHfxe" {
		t.Errorf("link %q", out.Link)
	}
	out.Link = ""
	h.desk.text = "пароль от почты hunter2"
	h.call("GET", "/api/paste", nil, &out)
	if out.Link != "" || out.Problem == nil {
		t.Errorf("clipboard text leaked: %+v", out)
	}
}

func TestOnlyThePageWithTheKeyGetsIn(t *testing.T) {
	h := newHarness(t, "http://127.0.0.1:1")
	for _, c := range []struct {
		name, host, auth string
		want             int
	}{
		{"no key", "", "", http.StatusUnauthorized},
		{"wrong key", "", "Bearer nope", http.StatusUnauthorized},
		{"rebound domain", "evil.example.com", "Bearer " + testToken, http.StatusForbidden},
		{"the page", "", "Bearer " + testToken, http.StatusOK},
	} {
		t.Run(c.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", h.srv.URL+"/api/state", nil)
			if c.host != "" {
				req.Host = c.host
			}
			if c.auth != "" {
				req.Header.Set("Authorization", c.auth)
			}
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Fatal(err)
			}
			resp.Body.Close()
			if resp.StatusCode != c.want {
				t.Fatalf("status %d, want %d", resp.StatusCode, c.want)
			}
		})
	}
	// The page itself carries nothing secret and loads without the key.
	resp, err := http.Get(h.srv.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK || !strings.Contains(string(body), "Проверка серверов") {
		t.Fatalf("index: %d", resp.StatusCode)
	}
	if csp := resp.Header.Get("Content-Security-Policy"); !strings.Contains(csp, "default-src 'self'") || strings.Contains(csp, "unsafe-inline") {
		t.Errorf("CSP %q", csp)
	}
}

func TestTheWindowAsksWithoutAKey(t *testing.T) {
	h := newHarness(t, "http://127.0.0.1:1")
	// The window's requests never cross the network: they arrive with the
	// webview's own host and no key, and the page and API answer them.
	for _, path := range []string{"/", "/api/state"} {
		req := httptest.NewRequest("GET", path, nil)
		req.Host = "wails.localhost"
		rec := httptest.NewRecorder()
		h.app.WindowHandler().ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Errorf("%s: %d", path, rec.Code)
		}
		if csp := rec.Header().Get("Content-Security-Policy"); strings.Contains(csp, "unsafe-inline") || csp == "" {
			t.Errorf("%s: CSP %q", path, csp)
		}
	}
	// Nothing to open before a run has a way out of its problem.
	req := httptest.NewRequest("POST", "/api/open", nil)
	rec := httptest.NewRecorder()
	h.app.WindowHandler().ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound || h.desk.opened != "" {
		t.Errorf("open: %d, opened %q", rec.Code, h.desk.opened)
	}
}

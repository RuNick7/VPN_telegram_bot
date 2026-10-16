package report

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
	"unicode/utf8"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/check"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/redact"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/subscription"
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

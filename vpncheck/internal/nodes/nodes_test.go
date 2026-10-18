package nodes

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/vpn-check/internal/nodelog"
)

const token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

var fp = strings.Repeat("ab", 32)

func TestParse(t *testing.T) {
	agents, errs := Parse("de1=https://" + token + "@de1.example.net:7443#" + fp + ",\n" +
		"v6=https://" + token + "@[2001:db8::1]:7443#" + fp + " " +
		"plain=http://" + token + "@x:1#" + fp + " nofp=https://" + token + "@x:1 =https://x")
	if len(agents) != 2 || agents[0].Name != "de1" || agents[0].URL != "https://de1.example.net:7443" ||
		agents[0].Token != token || hex.EncodeToString(agents[0].Fingerprint) != fp || agents[1].URL != "https://[2001:db8::1]:7443" {
		t.Fatalf("%+v", agents)
	}
	if len(errs) != 3 {
		t.Fatalf("%v", errs)
	}
	for _, err := range errs {
		if strings.Contains(err.Error(), token) {
			t.Errorf("token in %q", err)
		}
	}
	if agents, errs := Parse(""); agents != nil || errs != nil {
		t.Fatal("empty")
	}
}

func TestAsk(t *testing.T) {
	var got nodelog.Query
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer "+token {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		_ = json.NewDecoder(r.Body).Decode(&got)
		_ = json.NewEncoder(w).Encode(nodelog.Response{Node: "de1", Sections: []nodelog.Section{{Lines: []string{"line"}, Attributed: true}}})
	}))
	defer server.Close()
	sum := sha256.Sum256(server.Certificate().Raw)

	good := Agent{Name: "de1", URL: server.URL, Token: token, Fingerprint: sum[:]}
	impostor := Agent{Name: "fake", URL: server.URL, Token: token, Fingerprint: make([]byte, 32)}
	stale := Agent{Name: "old", URL: server.URL, Token: "other", Fingerprint: sum[:]}
	down := Agent{Name: "down", URL: "https://127.0.0.1:9", Token: token, Fingerprint: sum[:]}

	query := nodelog.Query{Windows: []nodelog.Window{{Server: "de1:443", From: time.Unix(0, 0), To: time.Unix(5, 0), Marker: "m.invalid"}}, SlackSeconds: 5}
	answers := Ask(context.Background(), []Agent{good, impostor, stale, down}, query, 5*time.Second)

	if answers[0].Err != nil || answers[0].Response.Node != "de1" || answers[0].Response.Sections[0].Lines[0] != "line" {
		t.Fatalf("good: %+v", answers[0])
	}
	if got.Windows[0].Marker != "m.invalid" || got.SlackSeconds != 5 {
		t.Fatalf("query %+v", got)
	}
	if !errors.Is(answers[1].Err, ErrFingerprint) {
		t.Errorf("impostor: %v", answers[1].Err)
	}
	if answers[2].Err == nil || !strings.HasPrefix(answers[2].Err.Error(), "HTTP 401") {
		t.Errorf("stale token: %v", answers[2].Err)
	}
	if answers[3].Err == nil {
		t.Error("down agent answered")
	}
}

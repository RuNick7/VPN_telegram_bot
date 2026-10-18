package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/vpn-check/internal/nodelog"
)

func init() { failedAuthDelay = 0 }

func testAgent(t *testing.T) *agent {
	t.Helper()
	path := filepath.Join(t.TempDir(), "access.log")
	line := "2026/10/16 20:00:03.000000 from 198.51.100.7:50002 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80 [in >> out] email: u-cust\n"
	if err := os.WriteFile(path, []byte(line), 0o644); err != nil {
		t.Fatal(err)
	}
	return &agent{name: "de1", logs: []string{path}, loc: time.UTC, token: "secret-token"}
}

func call(a *agent, method, path, token, body string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	if token != "" {
		r.Header.Set("Authorization", "Bearer "+token)
	}
	w := httptest.NewRecorder()
	a.routes().ServeHTTP(w, r)
	return w
}

const query = `{"windows":[{"server":"de1:443","from":"2026-10-16T20:00:00Z","to":"2026-10-16T20:00:04Z",` +
	`"marker":"vpncheck-0a1b2c3d-01.invalid","failed":false}],"users":[],"slack_seconds":5}`

func TestSearch(t *testing.T) {
	a := testAgent(t)
	w := call(a, http.MethodPost, "/v1/search", "secret-token", query)
	if w.Code != http.StatusOK {
		t.Fatalf("%d %s", w.Code, w.Body)
	}
	var got nodelog.Response
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got.Node != "de1" || len(got.Sections) != 1 || len(got.Sections[0].Lines) != 1 || got.Sections[0].Emails[0] != "u-cust" {
		t.Fatalf("%s", w.Body)
	}
}

func TestOnlyTheTokenGetsIn(t *testing.T) {
	a := testAgent(t)
	for _, token := range []string{"", "secret-tokeN", "secret-token-and-more"} {
		if w := call(a, http.MethodPost, "/v1/search", token, query); w.Code != http.StatusUnauthorized {
			t.Errorf("%q: %d", token, w.Code)
		}
		if w := call(a, http.MethodGet, "/v1/health", token, ""); w.Code != http.StatusUnauthorized {
			t.Errorf("%q health: %d", token, w.Code)
		}
	}
	if w := call(a, http.MethodGet, "/v1/search", "secret-token", ""); w.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET search: %d", w.Code)
	}
}

func TestBadQueriesAreRefused(t *testing.T) {
	a := testAgent(t)
	for _, body := range []string{
		`{}`,
		`{"windows":[],"extra":1}`,
		`{"windows":[{"from":"2026-10-16T20:00:00Z","to":"2026-10-17T20:00:00Z"}]}`,
		`not json`,
	} {
		if w := call(a, http.MethodPost, "/v1/search", "secret-token", body); w.Code != http.StatusBadRequest {
			t.Errorf("%s: %d", body, w.Code)
		}
	}
}

func TestHealthNamesUnreadableLogs(t *testing.T) {
	a := testAgent(t)
	a.logs = append(a.logs, filepath.Join(t.TempDir(), "missing.log"))
	w := call(a, http.MethodGet, "/v1/health", "secret-token", "")
	var got nodelog.Response
	_ = json.Unmarshal(w.Body.Bytes(), &got)
	if len(got.Files) != 2 || got.Files[0].Error != "" || got.Files[0].Size == 0 || got.Files[1].Error == "" {
		t.Fatalf("%s", w.Body)
	}
}

func TestCredentialsSurviveRestarts(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "agent")
	first, err := loadOrCreate(dir)
	if err != nil {
		t.Fatal(err)
	}
	again, err := loadOrCreate(dir)
	if err != nil {
		t.Fatal(err)
	}
	if first.token != again.token || first.fingerprint != again.fingerprint || len(first.token) < 40 {
		t.Fatalf("%+v %+v", first, again)
	}
	sum := sha256.Sum256(first.cert.Certificate[0])
	if first.fingerprint != hex.EncodeToString(sum[:]) {
		t.Fatal("fingerprint is not the certificate's sha256")
	}
	if info, _ := os.Stat(filepath.Join(dir, "key.pem")); info.Mode().Perm() != 0o600 {
		t.Errorf("key mode %v", info.Mode())
	}
	line := connectionLine("de1", first, "de1.example.net:7443")
	if line != "de1=https://"+first.token+"@de1.example.net:7443#"+first.fingerprint {
		t.Fatal(line)
	}
}

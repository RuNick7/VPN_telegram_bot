package app

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// The website's part: the subscription's status from our records, and the
// report into a support ticket.

type fakeSite struct {
	*httptest.Server
	mu     sync.Mutex
	status string // the status endpoint's JSON; empty answers 503
	sends  []sentReport
}

type sentReport struct{ link, summary, note, file string }

func newSite(t *testing.T, status string) *fakeSite {
	t.Helper()
	s := &fakeSite{status: status}
	s.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.mu.Lock()
		defer s.mu.Unlock()
		switch r.URL.Path {
		case "/api/vpncheck/status":
			if s.status == "" {
				w.WriteHeader(http.StatusServiceUnavailable)
				return
			}
			_, _ = io.WriteString(w, s.status)
		case "/api/vpncheck/report":
			file, _, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			data, _ := io.ReadAll(file)
			s.sends = append(s.sends, sentReport{r.FormValue("link"), r.FormValue("summary"), r.FormValue("note"), string(data)})
			w.WriteHeader(http.StatusCreated)
			_, _ = io.WriteString(w, `{"ticket_id":123,"created":true}`)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(s.Close)
	return s
}

func statusJSON(state string, expires time.Time) string {
	body := map[string]any{"state": state, "renew_url": "https://kairavpn.example/app/plans", "tier": "paid"}
	if !expires.IsZero() {
		body["expires_at"] = expires.Unix()
	}
	data, _ := json.Marshal(body)
	return string(data)
}

func TestSendingTheReportToSupport(t *testing.T) {
	web := internet(t)
	p := newPanel(t, map[string][]map[string]any{"🇩🇪 Германия": {vlessOutbound("proxy", vlessNode(t))}}, []string{"🇩🇪 Германия"})
	// The panel's date is the free tier's ten years out; the site's is real.
	p.headers["subscription-userinfo"] = "upload=0; download=0; total=0; expire=2100000000"
	paidUntil := time.Now().Add(40 * 24 * time.Hour)
	s := newSite(t, statusJSON("active", paidUntil))
	h := newHarness(t, web.URL)
	h.app.cfg.Site = s.URL

	var before state
	h.call("GET", "/api/state", nil, &before)
	if before.CanSend {
		t.Error("sending offered before any check")
	}
	h.call("POST", "/api/check", map[string]string{"link": p.link()}, nil)
	done := h.wait()
	if done.Phase != phaseDone || done.Card.Status != "Активна до "+day(paidUntil) || !done.CanSend {
		t.Fatalf("phase %q, card %+v, can send %v", done.Phase, done.Card, done.CanSend)
	}

	var after state
	if status := h.call("POST", "/api/send", map[string]string{"note": "Не грузит YouTube"}, &after); status != http.StatusOK {
		t.Fatalf("send: %d", status)
	}
	if after.Sent == nil || after.Sent.TicketID != 123 || !after.Sent.Created {
		t.Fatalf("sent %+v", after.Sent)
	}
	// A second press sends nothing more.
	h.call("POST", "/api/send", map[string]string{}, nil)
	if len(s.sends) != 1 {
		t.Fatalf("%d sends", len(s.sends))
	}
	sent := s.sends[0]
	if sent.link != p.link() || sent.note != "Не грузит YouTube" || !strings.Contains(sent.summary, "работает 1 из 1") {
		t.Errorf("%+v", sent)
	}
	if !strings.HasPrefix(sent.file, "Проверка серверов vpncheck ") {
		t.Errorf("file starts %q", sent.file[:min(80, len(sent.file))])
	}
	for _, secret := range []string{testUUID, "SayZcYcdx7zRHfxe"} {
		if strings.Contains(sent.file, secret) || strings.Contains(sent.summary, secret) {
			t.Errorf("the report sent holds %s", secret)
		}
	}
}

func TestAnExpiredSubscriptionIsNotChecked(t *testing.T) {
	web := internet(t)
	p := newPanel(t, map[string][]map[string]any{"🇩🇪 Германия": {vlessOutbound("proxy", vlessNode(t))}}, []string{"🇩🇪 Германия"})
	ended := time.Now().Add(-3 * 24 * time.Hour)
	s := newSite(t, statusJSON("expired", ended))
	h := newHarness(t, web.URL)
	h.app.cfg.Site = s.URL

	h.call("POST", "/api/check", map[string]string{"link": p.link()}, nil)
	done := h.wait()
	if done.Phase != phaseFailed || done.Problem == nil || done.Problem.Title != "Подписка закончилась "+day(ended) ||
		done.Problem.Link != "https://kairavpn.example/app/plans" || done.Problem.LinkText != "Продлить" {
		t.Fatalf("phase %q, problem %+v", done.Phase, done.Problem)
	}
	if done.Card.Tone != "bad" || done.CanSend {
		t.Errorf("card %+v, can send %v", done.Card, done.CanSend)
	}
	// The window opens «Продлить» through the app, and only that.
	if status := h.call("POST", "/api/open", nil, nil); status != http.StatusNoContent || h.desk.opened != "https://kairavpn.example/app/plans" {
		t.Errorf("open: %d, opened %q", status, h.desk.opened)
	}
	for _, server := range done.Servers {
		if server.State != "queued" {
			t.Errorf("a server was checked: %+v", server)
		}
	}
}

func TestTheFreeTierAndAnUnknownStatusAreSaidOnTheCard(t *testing.T) {
	web := internet(t)
	p := newPanel(t, map[string][]map[string]any{"🇩🇪 Германия": {vlessOutbound("proxy", vlessNode(t))}}, []string{"🇩🇪 Германия"})
	s := newSite(t, statusJSON("free", time.Now().Add(-24*time.Hour)))
	h := newHarness(t, web.URL)
	h.app.cfg.Site = s.URL

	h.call("POST", "/api/check", map[string]string{"link": p.link()}, nil)
	done := h.wait()
	if done.Phase != phaseDone || done.Card.Status != "Бесплатный тариф" || !strings.Contains(done.Card.Note, "часть серверов") {
		t.Fatalf("phase %q, card %+v", done.Phase, done.Card)
	}

	// The site down: the check goes on, and says payment is unknown.
	s.mu.Lock()
	s.status = ""
	s.mu.Unlock()
	h.call("POST", "/api/check", map[string]string{"link": p.link()}, nil)
	done = h.wait()
	if done.Phase != phaseDone || done.Card.Note != "Статус оплаты уточнить не удалось." || !done.CanSend {
		t.Fatalf("phase %q, card %+v, can send %v", done.Phase, done.Card, done.CanSend)
	}
}

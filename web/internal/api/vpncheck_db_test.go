package api

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// The vpncheck program's two endpoints against a real Postgres and a fake
// panel: a subscription link leads through the panel to our customer, and a
// report lands in their ticket.

type vpncheckEnv struct {
	*supportEnv
	// short UUID -> the panel account it belongs to
	accounts map[string]map[string]any
	address  string
}

func newVpncheckEnv(t *testing.T, freeTier bool) *vpncheckEnv {
	t.Helper()
	base := newSupportEnv(t)
	env := &vpncheckEnv{supportEnv: base, accounts: map[string]map[string]any{}}

	fake := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id, ok := strings.CutPrefix(r.URL.Path, "/api/users/by-short-uuid/")
		profile := env.accounts[id]
		if !ok || profile == nil {
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"message":"User not found"}`))
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"response": profile})
	}))
	t.Cleanup(fake.Close)
	client, err := panel.New(fake.URL, "token", "", "", 5*time.Second)
	if err != nil {
		t.Fatal(err)
	}

	cfg := &config.Config{BaseURL: "https://cabinet.example.com", SupportEnabled: true, FreeTierEnabled: freeTier}
	accounts := account.NewService(base.store, client, freeTier, 0, "internal", false, "")
	server := NewServer(cfg, base.store, auth.NewService(base.store, nil, cfg.BaseURL, time.Minute, time.Hour, ""),
		accounts, nil, slog.New(slog.NewTextHandler(io.Discard, nil)))
	base.server, base.handler = server, server.Routes()

	// An address of its own, so one test's attempts never count against
	// another's.
	raw := make([]byte, 2)
	_, _ = rand.Read(raw)
	env.address = "198.51." + hex.EncodeToString(raw[:1]) + "." + hex.EncodeToString(raw[1:])
	t.Cleanup(func() {
		_, _ = base.store.Pool().Exec(context.Background(),
			`DELETE FROM auth_rate_limits WHERE bucket = $1`, "vpncheck:"+env.address)
	})
	return env
}

// subscription gives a customer a panel account and returns its link.
func (e *vpncheckEnv) subscription(userID string, columns string, values ...any) string {
	e.t.Helper()
	raw := make([]byte, 8)
	_, _ = rand.Read(raw)
	id := hex.EncodeToString(raw)
	panelUUID := "3f0c" + hex.EncodeToString(raw[:2]) + "-0000-4000-8000-" + hex.EncodeToString(raw[2:8])
	e.accounts[id] = map[string]any{"uuid": panelUUID, "shortUuid": id, "username": "u-" + id}
	if columns != "" {
		args := append([]any{userID}, values...)
		if _, err := e.store.Pool().Exec(context.Background(),
			`UPDATE users SET `+columns+` WHERE id = $1`, args...); err != nil {
			e.t.Fatal(err)
		}
	}
	if _, err := e.store.Pool().Exec(context.Background(),
		`UPDATE users SET remnawave_uuid = $2 WHERE id = $1`, userID, panelUUID); err != nil {
		e.t.Fatal(err)
	}
	return "https://sub.example.com/" + id
}

func (e *vpncheckEnv) status(link string) *httptest.ResponseRecorder {
	e.t.Helper()
	body, _ := json.Marshal(map[string]string{"link": link})
	r := httptest.NewRequest(http.MethodPost, "/api/vpncheck/status", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r.RemoteAddr = e.address + ":5000"
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func (e *vpncheckEnv) report(link, note string, file string) *httptest.ResponseRecorder {
	e.t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	_ = form.WriteField("link", link)
	_ = form.WriteField("summary", "Отчёт проверки серверов (vpncheck 1.0): работает 1 из 2")
	if note != "" {
		_ = form.WriteField("note", note)
	}
	part, _ := form.CreateFormFile("file", "report.txt")
	_, _ = part.Write([]byte(file))
	_ = form.Close()
	r := httptest.NewRequest(http.MethodPost, "/api/vpncheck/report", &body)
	r.Header.Set("Content-Type", form.FormDataContentType())
	r.RemoteAddr = e.address + ":5000"
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

const vpncheckReport = "Проверка серверов vpncheck 1.0 (Xray 25.1)\nИтог: работает 1 из 2\n"

func TestVpncheckStatus(t *testing.T) {
	env := newVpncheckEnv(t, false)

	active, _ := env.customer()
	link := env.subscription(active, `subscription_ends = now() + interval '10 days 2 hours', squad_tier = 'paid'`)
	got := decode[vpncheckStatusBody](t, env.status(link))
	if got.State != "active" || got.DaysLeft != 11 || got.ExpiresAt == nil || got.Tier != "paid" ||
		got.RenewURL != "https://cabinet.example.com/app/plans" {
		t.Errorf("active: %+v", got)
	}

	lapsed, _ := env.customer()
	got = decode[vpncheckStatusBody](t, env.status(env.subscription(lapsed, `subscription_ends = now() - interval '3 days'`)))
	if got.State != "expired" || got.DaysLeft != 0 || got.ExpiresAt == nil {
		t.Errorf("expired: %+v", got)
	}

	never, _ := env.customer()
	got = decode[vpncheckStatusBody](t, env.status(env.subscription(never, "")))
	if got.State != "none" || got.ExpiresAt != nil {
		t.Errorf("never: %+v", got)
	}

	if r := env.status("https://sub.example.com/NoSuchSubscription"); r.Code != http.StatusNotFound ||
		!strings.Contains(r.Body.String(), "subscription_not_found") {
		t.Errorf("unknown: %d %s", r.Code, r.Body)
	}
	if r := env.status("vless://nope"); r.Code != http.StatusBadRequest {
		t.Errorf("not a link: %d %s", r.Code, r.Body)
	}
}

func TestVpncheckStatusOnTheFreeTier(t *testing.T) {
	env := newVpncheckEnv(t, true)
	lapsed, _ := env.customer()
	got := decode[vpncheckStatusBody](t, env.status(env.subscription(lapsed, `subscription_ends = now() - interval '3 days'`)))
	if got.State != "free" {
		t.Errorf("%+v", got)
	}
}

// A panel account named the old way, `str(telegram_id)`, belongs to whoever
// has that Telegram id -- and once merged, to the account it was merged into.
func TestVpncheckFindsLegacyAndMergedAccounts(t *testing.T) {
	env := newVpncheckEnv(t, false)
	ctx := context.Background()
	survivor, _ := env.customer()
	absorbed, _ := env.customer()
	telegramID := time.Now().UnixNano() % 1_000_000_000_000
	if _, err := env.store.Pool().Exec(ctx,
		`UPDATE users SET telegram_id = $2, merged_into = $3 WHERE id = $1`, absorbed, telegramID, survivor); err != nil {
		t.Fatal(err)
	}
	if _, err := env.store.Pool().Exec(ctx,
		`UPDATE users SET subscription_ends = now() + interval '5 days' WHERE id = $1`, survivor); err != nil {
		t.Fatal(err)
	}
	env.accounts["LegacyAccount01"] = map[string]any{"uuid": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
		"shortUuid": "LegacyAccount01", "username": strconv.FormatInt(telegramID, 10)}

	got := decode[vpncheckStatusBody](t, env.status("https://sub.example.com/LegacyAccount01"))
	if got.State != "active" || got.DaysLeft != 5 {
		t.Errorf("%+v", got)
	}
}

func TestVpncheckReportGoesIntoATicket(t *testing.T) {
	env := newVpncheckEnv(t, false)
	ctx := context.Background()
	userID, token := env.customer()
	link := env.subscription(userID, "")
	id := link[strings.LastIndex(link, "/")+1:]

	// No ticket open: one is opened for the report.
	r := env.report(link, "Не открывается YouTube", vpncheckReport+"Подписка "+link+"\n")
	if r.Code != http.StatusCreated {
		t.Fatalf("%d %s", r.Code, r.Body)
	}
	first := decode[struct {
		TicketID int64 `json:"ticket_id"`
		Created  bool  `json:"created"`
	}](t, r)
	if !first.Created {
		t.Errorf("%+v", first)
	}
	thread := decode[threadResponse](t, env.get(ticketPath(first.TicketID, ""), token))
	if thread.Ticket.Subject != support.ReportSubject || thread.Ticket.Status != "open" || len(thread.Messages) != 1 {
		t.Fatalf("%+v", thread)
	}
	message := thread.Messages[0]
	if message.Author != "user" || !strings.HasPrefix(message.Body, "Не открывается YouTube\n\n🩺 Отчёт проверки") {
		t.Errorf("body %q", message.Body)
	}
	file := env.get(message.Attachments[0].URL, token)
	if message.Attachments[0].Name != support.ReportFileName || strings.Contains(file.Body.String(), id) ||
		!strings.Contains(file.Body.String(), "[скрыто:подписка]") {
		t.Errorf("file %q: %s", message.Attachments[0].Name, file.Body)
	}

	// One open: the next report goes into it, the latest touched.
	second := env.open(token, "Медленно")
	r = env.report(link, "", vpncheckReport)
	got := decode[struct {
		TicketID int64 `json:"ticket_id"`
		Created  bool  `json:"created"`
	}](t, r)
	if r.Code != http.StatusCreated || got.Created || got.TicketID != second {
		t.Errorf("%d %+v, want ticket %d", r.Code, got, second)
	}

	var reports, pending int
	_ = env.store.Pool().QueryRow(ctx,
		`SELECT COUNT(*), COUNT(*) FILTER (WHERE node_logs_at IS NULL AND message_id IS NOT NULL)
		 FROM vpncheck_reports r JOIN support_tickets t ON t.id = r.ticket_id WHERE t.user_id = $1`,
		userID).Scan(&reports, &pending)
	if reports != 2 || pending != 2 {
		t.Errorf("rows %d, pending %d", reports, pending)
	}
}

func TestVpncheckReportLimits(t *testing.T) {
	env := newVpncheckEnv(t, false)
	userID, _ := env.customer()
	link := env.subscription(userID, "")
	for i := range support.ReportsPerDay {
		if r := env.report(link, "", vpncheckReport); r.Code != http.StatusCreated {
			t.Fatalf("report %d: %d %s", i+1, r.Code, r.Body)
		}
	}
	if r := env.report(link, "", vpncheckReport); r.Code != http.StatusTooManyRequests ||
		!strings.Contains(r.Body.String(), "report_quota") {
		t.Errorf("over the day's reports: %d %s", r.Code, r.Body)
	}
	if r := env.report("https://sub.example.com/NoSuchSubscription", "", vpncheckReport); r.Code != http.StatusNotFound {
		t.Errorf("unknown link: %d %s", r.Code, r.Body)
	}
	if r := env.report(link, "", "просто текст"); r.Code != http.StatusUnsupportedMediaType {
		t.Errorf("not a report: %d %s", r.Code, r.Body)
	}

	env.server.cfg.SupportEnabled = false
	if r := env.report(link, "", vpncheckReport); r.Code != http.StatusNotFound {
		t.Errorf("support off: %d %s", r.Code, r.Body)
	}
}

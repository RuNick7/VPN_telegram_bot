package api

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// Server-check reports sent with a one-time code, against a real Postgres.
// The code is granted here the way user_bot grants it: a row with its hash.

func (e *supportEnv) grantDiagnostics(ticketID int64, code string, expiresIn string) {
	e.t.Helper()
	sum := sha256.Sum256([]byte(strings.ReplaceAll(code, "-", "")))
	if _, err := e.store.Pool().Exec(context.Background(),
		`INSERT INTO support_diagnostics (ticket_id, requested_by, decision, decided_at, code_hash, code_expires_at)
		 VALUES ($1, 111, 'granted', now(), $2, now() + $3::interval)`,
		ticketID, sum[:], expiresIn); err != nil {
		e.t.Fatal(err)
	}
}

// newDiagnosticsCode is a fresh code per test, so a row some other run left
// behind in a shared test database cannot collide on code_hash.
func newDiagnosticsCode(t *testing.T) string {
	t.Helper()
	raw := make([]byte, support.DiagnosticsCodeLen)
	if _, err := rand.Read(raw); err != nil {
		t.Fatal(err)
	}
	for i, b := range raw {
		raw[i] = support.DiagnosticsAlphabet[int(b)%len(support.DiagnosticsAlphabet)]
	}
	return string(raw[0:4]) + "-" + string(raw[4:8]) + "-" + string(raw[8:12])
}

func (e *supportEnv) diagnosticsSession(code string) *httptest.ResponseRecorder {
	e.t.Helper()
	body, _ := json.Marshal(map[string]string{"code": code})
	r := httptest.NewRequest(http.MethodPost, "/api/support/diagnostics/session", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r.RemoteAddr = "192.0.2.10:5000"
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func (e *supportEnv) diagnosticsReport(code string, file []byte) *httptest.ResponseRecorder {
	e.t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	_ = form.WriteField("code", code)
	_ = form.WriteField("summary", "Отчёт проверки серверов (vpncheck 1.0): работает 1 из 2 серверов")
	part, _ := form.CreateFormFile("file", "report.txt")
	_, _ = part.Write(file)
	_ = form.Close()
	r := httptest.NewRequest(http.MethodPost, "/api/support/diagnostics/report", &body)
	r.Header.Set("Content-Type", form.FormDataContentType())
	r.RemoteAddr = "192.0.2.10:5000"
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func (e *supportEnv) forgetDiagnosticsAttempts() {
	e.t.Cleanup(func() {
		_, _ = e.store.Pool().Exec(context.Background(),
			`DELETE FROM auth_rate_limits WHERE bucket LIKE 'support-diagnostics:%'`)
	})
}

func TestDiagnosticsReportLandsInTheTicketOnce(t *testing.T) {
	e := newSupportEnv(t)
	e.forgetDiagnosticsAttempts()
	userID, token := e.customer()
	ticketID := e.open(token, "Не работает VPN")
	code := newDiagnosticsCode(t)
	e.grantDiagnostics(ticketID, code, "1 hour")

	if response := e.diagnosticsSession("ZZZZ-ZZZZ-ZZZZ"); response.Code != http.StatusNotFound {
		t.Fatalf("unknown code: %d", response.Code)
	}
	response := e.diagnosticsSession(strings.ToLower(strings.ReplaceAll(code, "-", " ")))
	if response.Code != http.StatusOK {
		t.Fatalf("session: %d %s", response.Code, response.Body)
	}
	var session diagnosticsSessionBody
	_ = json.Unmarshal(response.Body.Bytes(), &session)
	if session.TicketID != ticketID || session.Subject != "Не работает VPN" {
		t.Fatalf("%+v", session)
	}

	report := []byte("Проверка серверов vpncheck\nИтог: работает 1 из 2\n")
	if response := e.diagnosticsReport(code, report); response.Code != http.StatusCreated {
		t.Fatalf("report: %d %s", response.Code, response.Body)
	}
	// Spent: neither endpoint takes it again.
	if response := e.diagnosticsReport(code, report); response.Code != http.StatusNotFound {
		t.Fatalf("replayed report: %d", response.Code)
	}
	if response := e.diagnosticsSession(code); response.Code != http.StatusNotFound {
		t.Fatalf("spent session: %d", response.Code)
	}

	// The customer sees it in their thread as their own message, with the file.
	_, messages, err := e.store.SupportThread(context.Background(), userID, ticketID)
	if err != nil {
		t.Fatal(err)
	}
	last := messages[len(messages)-1]
	if last.Author != "user" || !strings.HasPrefix(last.Body, "🩺 Отчёт проверки серверов") {
		t.Fatalf("%+v", last)
	}
	if len(last.Attachments) != 1 || last.Attachments[0].FileName != "vpncheck-report.txt" ||
		last.Attachments[0].SizeBytes != int64(len(report)) {
		t.Fatalf("%+v", last.Attachments)
	}
	// And it waits for the operators like any message from the customer.
	var undelivered bool
	_ = e.store.Pool().QueryRow(context.Background(),
		`SELECT delivered_at IS NULL FROM support_messages WHERE id = $1`, last.ID).Scan(&undelivered)
	if !undelivered {
		t.Fatal("the report is not in the outbox")
	}
}

func TestDiagnosticsCodeThatExpiredOrWhoseTicketClosed(t *testing.T) {
	e := newSupportEnv(t)
	e.forgetDiagnosticsAttempts()
	_, token := e.customer()

	expired := e.open(token, "Старое")
	code := newDiagnosticsCode(t)
	e.grantDiagnostics(expired, code, "-1 minute")
	if response := e.diagnosticsReport(code, []byte("text")); response.Code != http.StatusNotFound {
		t.Fatalf("expired code: %d", response.Code)
	}

	closed := e.open(token, "Закрытое")
	code = newDiagnosticsCode(t)
	e.grantDiagnostics(closed, code, "1 hour")
	if response := e.send(http.MethodPost, "/api/support/tickets/"+strconv.FormatInt(closed, 10)+"/close", token, nil); response.Code != http.StatusOK {
		t.Fatalf("close: %d", response.Code)
	}
	if response := e.diagnosticsReport(code, []byte("text")); response.Code != http.StatusConflict {
		t.Fatalf("closed ticket: %d", response.Code)
	}
}

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
	"net/url"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// Support tickets against a real Postgres.
//
// The rest of this package's tests need no database. These cannot do without
// one: what is worth pinning -- that a ticket which is not yours does not
// exist, that the limits count, that a file comes back byte for byte and by
// range -- lives in SQL. They run only when TEST_DATABASE_URL names a
// disposable database, the same rule the Python suite enforces, and remove
// every row they create.

var png = []byte("\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + strings.Repeat("\x00", 200))

type supportEnv struct {
	t       *testing.T
	store   *store.Store
	server  *Server
	handler http.Handler
}

func newSupportEnv(t *testing.T) *supportEnv {
	t.Helper()
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL is not set")
	}
	parsed, err := url.Parse(dsn)
	if err != nil || !strings.Contains(strings.ToLower(parsed.Path), "test") {
		t.Fatalf("refusing to run against %q: the database name must contain \"test\"", parsed.Path)
	}

	st, err := store.Open(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(st.Close)

	cfg := &config.Config{BaseURL: "https://cabinet.example.com", SupportEnabled: true}
	server := NewServer(cfg, st, auth.NewService(st, nil, cfg.BaseURL, time.Minute, time.Hour, ""),
		nil, nil, slog.New(slog.NewTextHandler(io.Discard, nil)))
	return &supportEnv{t: t, store: st, server: server, handler: server.Routes()}
}

// customer creates an account with a live session and returns its session
// token. The account, and everything hanging off it, goes when the test ends.
func (e *supportEnv) customer() (userID, token string) {
	e.t.Helper()
	ctx := context.Background()
	raw := make([]byte, 16)
	_, _ = rand.Read(raw)
	token = hex.EncodeToString(raw)

	if err := e.store.Pool().QueryRow(ctx,
		`INSERT INTO users (email) VALUES ($1) RETURNING id`, token+"@support.test").Scan(&userID); err != nil {
		e.t.Fatal(err)
	}
	if err := e.store.CreateSession(ctx, token, userID, time.Hour, "test", "127.0.0.1"); err != nil {
		e.t.Fatal(err)
	}
	e.t.Cleanup(func() {
		_, _ = e.store.Pool().Exec(ctx, `DELETE FROM users WHERE id = $1`, userID)
		_, _ = e.store.Pool().Exec(ctx, `DELETE FROM auth_rate_limits WHERE bucket LIKE '%' || $1`, userID)
	})
	return userID, token
}

type upload struct{ name, content string }

func (e *supportEnv) send(method, target, token string, fields map[string]string, files ...upload) *httptest.ResponseRecorder {
	e.t.Helper()
	var body io.Reader
	contentType := ""
	if fields != nil || files != nil {
		var buffer bytes.Buffer
		writer := multipart.NewWriter(&buffer)
		for name, value := range fields {
			_ = writer.WriteField(name, value)
		}
		for _, f := range files {
			part, _ := writer.CreateFormFile("files", f.name)
			_, _ = part.Write([]byte(f.content))
		}
		_ = writer.Close()
		body, contentType = &buffer, writer.FormDataContentType()
	}
	r := httptest.NewRequest(method, target, body)
	if contentType != "" {
		r.Header.Set("Content-Type", contentType)
	}
	if token != "" {
		r.AddCookie(&http.Cookie{Name: SessionCookie, Value: token})
	}
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func (e *supportEnv) get(target, token string, header ...string) *httptest.ResponseRecorder {
	e.t.Helper()
	r := httptest.NewRequest(http.MethodGet, target, nil)
	r.AddCookie(&http.Cookie{Name: SessionCookie, Value: token})
	for i := 0; i+1 < len(header); i += 2 {
		r.Header.Set(header[i], header[i+1])
	}
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func (e *supportEnv) open(token, subject string, files ...upload) int64 {
	e.t.Helper()
	response := e.send(http.MethodPost, "/api/support/tickets", token,
		map[string]string{"subject": subject, "body": "Не подключается после обновления"}, files...)
	if response.Code != http.StatusCreated {
		e.t.Fatalf("opening a ticket: %d %s", response.Code, response.Body)
	}
	var created struct{ ID int64 }
	_ = json.Unmarshal(response.Body.Bytes(), &created)
	return created.ID
}

type threadResponse struct {
	Ticket   supportTicketBody    `json:"ticket"`
	Messages []supportMessageBody `json:"messages"`
}

func decode[T any](t *testing.T, recorder *httptest.ResponseRecorder) T {
	t.Helper()
	var value T
	if err := json.Unmarshal(recorder.Body.Bytes(), &value); err != nil {
		t.Fatalf("decoding %q: %v", recorder.Body, err)
	}
	return value
}

func ticketPath(id int64, suffix string) string {
	return "/api/support/tickets/" + strconv.FormatInt(id, 10) + suffix
}

// -- the customer's round trip --------------------------------------------------

func TestATicketGoesAllTheWayRound(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()

	id := env.open(token, "Не подключается", upload{"скриншот.png", string(png)})

	list := decode[struct{ Tickets []supportTicketBody }](t, env.get("/api/support/tickets", token))
	if len(list.Tickets) != 1 || list.Tickets[0].ID != id || list.Tickets[0].Status != "open" {
		t.Fatalf("list: %+v", list.Tickets)
	}

	thread := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
	if len(thread.Messages) != 1 || thread.Messages[0].Author != "user" {
		t.Fatalf("thread: %+v", thread.Messages)
	}
	attachment := thread.Messages[0].Attachments[0]
	if attachment.Name != "скриншот.png" || attachment.Kind != "image" || attachment.URL == "" {
		t.Fatalf("attachment: %+v", attachment)
	}

	file := env.get(attachment.URL, token)
	if file.Code != http.StatusOK || !bytes.Equal(file.Body.Bytes(), png) {
		t.Fatalf("download: %d, %d bytes", file.Code, file.Body.Len())
	}
	if got := file.Header().Get("Content-Type"); got != "image/png" {
		t.Errorf("served as %q", got)
	}
	if got := file.Header().Get("Content-Disposition"); !strings.HasPrefix(got, "inline;") {
		t.Errorf("disposition %q", got)
	}

	// What a video player does, and what Safari insists on.
	partial := env.get(attachment.URL, token, "Range", "bytes=8-15")
	if partial.Code != http.StatusPartialContent || !bytes.Equal(partial.Body.Bytes(), png[8:16]) {
		t.Errorf("range: %d %q", partial.Code, partial.Body.Bytes())
	}

	if reply := env.send(http.MethodPost, ticketPath(id, "/messages"), token,
		map[string]string{"body": "Ещё деталь"}); reply.Code != http.StatusCreated {
		t.Fatalf("reply: %d %s", reply.Code, reply.Body)
	}
	if closed := env.send(http.MethodPost, ticketPath(id, "/close"), token, nil); closed.Code != http.StatusOK {
		t.Fatalf("close: %d %s", closed.Code, closed.Body)
	}
	late := env.send(http.MethodPost, ticketPath(id, "/messages"), token, map[string]string{"body": "ещё"})
	if late.Code != http.StatusConflict {
		t.Errorf("writing to a closed ticket: %d", late.Code)
	}
}

func TestFilesKeepTheOrderTheyWereAttachedIn(t *testing.T) {
	// They are written in one transaction, where now() is one instant for
	// every row; ordered by that and a random UUID, a screenshot and the
	// recording that explains it came back in whichever order they liked.
	env := newSupportEnv(t)
	_, token := env.customer()
	names := []string{"1.png", "2.png", "3.png"}
	id := env.open(token, "Порядок", upload{names[0], string(png)}, upload{names[1], string(png)}, upload{names[2], string(png)})

	for round := 0; round < 3; round++ {
		thread := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
		for i, attachment := range thread.Messages[0].Attachments {
			if attachment.Name != names[i] {
				t.Fatalf("file %d is %q, want %q", i, attachment.Name, names[i])
			}
		}
	}
}

func TestAnotherCustomersTicketDoesNotExist(t *testing.T) {
	env := newSupportEnv(t)
	_, owner := env.customer()
	_, stranger := env.customer()

	id := env.open(owner, "Моё", upload{"a.png", string(png)})
	thread := decode[threadResponse](t, env.get(ticketPath(id, ""), owner))
	fileURL := thread.Messages[0].Attachments[0].URL

	for name, response := range map[string]*httptest.ResponseRecorder{
		"thread":   env.get(ticketPath(id, ""), stranger),
		"file":     env.get(fileURL, stranger),
		"reply":    env.send(http.MethodPost, ticketPath(id, "/messages"), stranger, map[string]string{"body": "x"}),
		"close":    env.send(http.MethodPost, ticketPath(id, "/close"), stranger, nil),
		"bad id":   env.get("/api/support/attachments/not-a-uuid", owner),
		"bad num":  env.get("/api/support/tickets/-1", owner),
		"no login": env.get(ticketPath(id, ""), "nobody"),
	} {
		want := http.StatusNotFound
		if name == "no login" {
			want = http.StatusUnauthorized
		}
		if response.Code != want {
			t.Errorf("%s: %d, want %d", name, response.Code, want)
		}
	}
	list := decode[struct{ Tickets []supportTicketBody }](t, env.get("/api/support/tickets", stranger))
	if len(list.Tickets) != 0 {
		t.Errorf("the stranger sees %d tickets", len(list.Tickets))
	}
}

func TestOnlyAFewTicketsCanBeOpenAtOnce(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()
	var first int64
	for i := 0; i < support.MaxOpenTickets; i++ {
		id := env.open(token, "Тема "+strconv.Itoa(i))
		if i == 0 {
			first = id
		}
	}

	extra := env.send(http.MethodPost, "/api/support/tickets", token,
		map[string]string{"subject": "Ещё одна", "body": "x"})
	if extra.Code != http.StatusConflict {
		t.Fatalf("a ticket past the limit: %d", extra.Code)
	}

	env.send(http.MethodPost, ticketPath(first, "/close"), token, nil)
	env.open(token, "Теперь можно")
}

func TestAnOperatorsAnswerLightsTheDotUntilItIsRead(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()
	id := env.open(token, "Оплата")

	// What admin_bot writes when an operator replies in Telegram.
	if _, err := env.store.Pool().Exec(context.Background(),
		`INSERT INTO support_messages (ticket_id, author, admin_telegram_id, body) VALUES ($1, 'admin', 1, 'Ответ')`,
		id); err != nil {
		t.Fatal(err)
	}

	unread := func() int {
		return decode[meBody](t, env.get("/api/me", token)).SupportUnread
	}
	if unread() != 1 {
		t.Fatalf("unread = %d after an answer", unread())
	}

	thread := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
	if !thread.Ticket.Unread || thread.Messages[1].Author != "support" {
		t.Errorf("the thread should flag the answer it is showing: %+v", thread.Ticket)
	}
	if unread() != 0 {
		t.Errorf("unread = %d after opening the thread", unread())
	}
}

func TestAFileTheThreadDoesNotShowIsADownload(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()
	id := env.open(token, "Документ", upload{"счёт.pdf", "%PDF-1.7\n%...."})

	// An operator can send anything from Telegram, an HTML page included.
	var messageID int64
	ctx := context.Background()
	_ = env.store.Pool().QueryRow(ctx,
		`INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'admin', '') RETURNING id`, id).Scan(&messageID)
	page := []byte("<script>alert(1)</script>")
	var attachmentID string
	_ = env.store.Pool().QueryRow(ctx,
		`INSERT INTO support_attachments (message_id, file_name, content_type, size_bytes)
		 VALUES ($1, 'page.html', 'text/html', $2) RETURNING id`, messageID, len(page)).Scan(&attachmentID)
	_, _ = env.store.Pool().Exec(ctx,
		`INSERT INTO support_attachment_data (attachment_id, data) VALUES ($1, $2)`, attachmentID, page)

	thread := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
	pdf := env.get(thread.Messages[0].Attachments[0].URL, token)
	if pdf.Header().Get("Content-Type") != "application/pdf" ||
		!strings.HasPrefix(pdf.Header().Get("Content-Disposition"), "attachment;") {
		t.Errorf("pdf served as %q, %q", pdf.Header().Get("Content-Type"), pdf.Header().Get("Content-Disposition"))
	}

	served := env.get("/api/support/attachments/"+attachmentID, token)
	if got := served.Header().Get("Content-Type"); got != "application/octet-stream" {
		t.Errorf("an HTML page was served as %q", got)
	}
	if !bytes.Equal(served.Body.Bytes(), page) {
		t.Errorf("body %q", served.Body.Bytes())
	}
	if got := served.Header().Get("Content-Security-Policy"); !strings.Contains(got, "sandbox") {
		t.Errorf("no sandbox on a file response: %q", got)
	}
	if thread.Messages[1].Attachments[0].Kind != "file" {
		t.Error("the page would try to draw an HTML file as a picture")
	}
}

func TestAnExpiredFileSaysSo(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()
	id := env.open(token, "Старое", upload{"a.png", string(png)})
	thread := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
	fileURL := thread.Messages[0].Attachments[0].URL

	ctx := context.Background()
	_, _ = env.store.Pool().Exec(ctx,
		`UPDATE support_tickets SET updated_at = now() - interval '100 days' WHERE id = $1`, id)
	purged, err := env.store.PurgeStaleSupportAttachments(ctx, support.AttachmentRetention)
	if err != nil || purged < 1 {
		t.Fatalf("purged %d, %v", purged, err)
	}

	if gone := env.get(fileURL, token); gone.Code != http.StatusGone {
		t.Errorf("an expired file answered %d", gone.Code)
	}
	after := decode[threadResponse](t, env.get(ticketPath(id, ""), token))
	if a := after.Messages[0].Attachments[0]; a.Available || a.URL != "" {
		t.Errorf("an expired file is still offered: %+v", a)
	}
}

func TestTheDailyUploadAllowanceIsCounted(t *testing.T) {
	env := newSupportEnv(t)
	userID, _ := env.customer()
	file := []store.NewSupportFile{{FileName: "a.png", ContentType: "image/png", Data: png}}
	ctx := context.Background()

	if _, err := env.store.CreateSupportTicket(ctx, userID, "Первый", "x", file, 3, int64(len(png))); err != nil {
		t.Fatal(err)
	}
	_, err := env.store.CreateSupportTicket(ctx, userID, "Второй", "x", file, 3, int64(len(png)))
	if err != store.ErrUploadQuota {
		t.Errorf("got %v, want the quota to bite", err)
	}
}

func TestTheSectionIsHiddenWhileSwitchedOff(t *testing.T) {
	env := newSupportEnv(t)
	_, token := env.customer()
	env.server.cfg.SupportEnabled = false

	if response := env.get("/api/support/tickets", token); response.Code != http.StatusNotFound {
		t.Errorf("list answered %d", response.Code)
	}
	if unread := decode[meBody](t, env.get("/api/me", token)).SupportUnread; unread != 0 {
		t.Errorf("unread = %d", unread)
	}
}

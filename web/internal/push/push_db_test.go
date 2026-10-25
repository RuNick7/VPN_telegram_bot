package push

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"log/slog"
	"net/url"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/webpush"
)

// The dispatcher against a real Postgres: what it picks up lives in SQL.
// Runs only when TEST_DATABASE_URL names a disposable database.

type fakeSender struct {
	mu   sync.Mutex
	sent map[string][]webpush.Message // by endpoint
	fail map[string]error
}

func (f *fakeSender) Send(_ context.Context, sub webpush.Subscription, msg webpush.Message, _ time.Duration) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if err := f.fail[sub.Endpoint]; err != nil {
		return err
	}
	f.sent[sub.Endpoint] = append(f.sent[sub.Endpoint], msg)
	return nil
}

type env struct {
	t      *testing.T
	store  *store.Store
	sender *fakeSender
	svc    *Service
}

func newEnv(t *testing.T) *env {
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
	sender := &fakeSender{sent: map[string][]webpush.Message{}, fail: map[string]error{}}
	return &env{t: t, store: st, sender: sender, svc: &Service{
		store: st, sender: sender, log: slog.New(slog.NewTextHandler(io.Discard, nil)),
	}}
}

func (e *env) exec(sql string, args ...any) {
	e.t.Helper()
	if _, err := e.store.Pool().Exec(context.Background(), sql, args...); err != nil {
		e.t.Fatalf("%s: %v", sql, err)
	}
}

// customer makes an account whose subscription ends `left` from now, with one
// browser. Returns the account and the browser's endpoint.
func (e *env) customer(left time.Duration) (string, string) {
	e.t.Helper()
	raw := make([]byte, 8)
	_, _ = rand.Read(raw)
	name := hex.EncodeToString(raw)
	var id string
	if err := e.store.Pool().QueryRow(context.Background(),
		`INSERT INTO users (email, subscription_ends) VALUES ($1, now() + make_interval(secs => $2)) RETURNING id`,
		name+"@push.test", left.Seconds()).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	e.t.Cleanup(func() {
		ctx := context.Background()
		_, _ = e.store.Pool().Exec(ctx, `DELETE FROM payments WHERE user_id = $1`, id)
		_, _ = e.store.Pool().Exec(ctx, `DELETE FROM users WHERE id = $1`, id)
	})
	endpoint := "https://fcm.googleapis.com/fcm/send/" + name
	if err := e.store.SavePushSubscription(context.Background(), id, endpoint, "key", "auth"); err != nil {
		e.t.Fatal(err)
	}
	return id, endpoint
}

func (e *env) pass() {
	e.t.Helper()
	if err := e.svc.pass(context.Background()); err != nil {
		e.t.Fatal(err)
	}
}

func (e *env) titles(endpoint string) []string {
	var out []string
	for _, m := range e.sender.sent[endpoint] {
		out = append(out, m.Title)
	}
	return out
}

func TestExpiryIsSentOncePerStage(t *testing.T) {
	e := newEnv(t)
	_, threeDays := e.customer(60 * time.Hour)
	_, oneDay := e.customer(5 * time.Hour)
	_, farOff := e.customer(20 * 24 * time.Hour)
	_, expired := e.customer(-time.Hour)

	e.pass()
	e.pass() // a second pass sends nothing new

	if got := e.titles(threeDays); len(got) != 1 || got[0] != "Подписка заканчивается" {
		t.Errorf("three days out: %v", got)
	}
	if got := e.titles(oneDay); len(got) != 1 {
		t.Errorf("hours out: %v", got)
	}
	if got := e.titles(farOff); len(got) != 0 {
		t.Errorf("weeks out: %v", got)
	}
	if got := e.titles(expired); len(got) != 0 {
		t.Errorf("already over: %v", got)
	}
}

func TestTheOneDayReminderFollowsTheThreeDayOne(t *testing.T) {
	e := newEnv(t)
	// Two days ago the three-day reminder went out for this same end date.
	id, endpoint := e.customer(5 * time.Hour)
	e.exec(`INSERT INTO push_sent (user_id, event_key)
	        SELECT id, 'expiry:' || EXTRACT(EPOCH FROM subscription_ends)::bigint || ':3' FROM users WHERE id = $1`, id)
	e.pass()
	e.pass()
	if got := e.titles(endpoint); len(got) != 1 {
		t.Errorf("want the one-day reminder once, got %v", got)
	}
}

func TestRenewingStartsTheRemindersAgain(t *testing.T) {
	e := newEnv(t)
	id, endpoint := e.customer(60 * time.Hour)
	e.pass()
	e.exec(`UPDATE users SET subscription_ends = subscription_ends + interval '30 days' WHERE id = $1`, id)
	e.pass()
	if got := e.titles(endpoint); len(got) != 1 {
		t.Errorf("renewed far ahead: %v", got)
	}
	e.exec(`UPDATE users SET subscription_ends = now() + interval '50 hours' WHERE id = $1`, id)
	e.pass()
	if got := e.titles(endpoint); len(got) != 2 {
		t.Errorf("new period nearing its end: %v", got)
	}
}

func TestPreferencesAreHonoured(t *testing.T) {
	e := newEnv(t)
	id, endpoint := e.customer(60 * time.Hour)
	if err := e.store.SetPushPreferences(context.Background(), id,
		store.PushPreferences{Expiry: false, Support: true, Payment: true}); err != nil {
		t.Fatal(err)
	}
	e.pass()
	if got := e.titles(endpoint); len(got) != 0 {
		t.Errorf("expiry switched off, still sent: %v", got)
	}
}

func TestSupportAnswersAreSentUntilRead(t *testing.T) {
	e := newEnv(t)
	id, endpoint := e.customer(30 * 24 * time.Hour)
	var ticket, readTicket int64
	ctx := context.Background()
	_ = e.store.Pool().QueryRow(ctx,
		`INSERT INTO support_tickets (user_id, subject, user_read_at) VALUES ($1, 'Не работает', now() - interval '1 hour') RETURNING id`, id).Scan(&ticket)
	_ = e.store.Pool().QueryRow(ctx,
		`INSERT INTO support_tickets (user_id, subject, user_read_at) VALUES ($1, 'Прочитано', now() + interval '1 minute') RETURNING id`, id).Scan(&readTicket)
	e.exec(`INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'admin', 'секретный ответ')`, ticket)
	e.exec(`INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'user', 'вопрос')`, ticket)
	e.exec(`INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'admin', 'уже прочитан')`, readTicket)
	e.exec(`INSERT INTO support_messages (ticket_id, author, body, created_at) VALUES ($1, 'admin', 'старый', now() - interval '3 days')`, ticket)

	e.pass()
	e.pass()
	sent := e.sender.sent[endpoint]
	if len(sent) != 1 || sent[0].Title != "Ответ поддержки" {
		t.Fatalf("sent %+v", sent)
	}
	if strings.Contains(sent[0].Body, "секретный") {
		t.Error("the answer itself went into the notification")
	}
}

func TestPaymentsAreOffByDefault(t *testing.T) {
	e := newEnv(t)
	quiet, quietEndpoint := e.customer(30 * 24 * time.Hour)
	loud, loudEndpoint := e.customer(30 * 24 * time.Hour)
	if err := e.store.SetPushPreferences(context.Background(), loud, store.PushPreferences{Payment: true}); err != nil {
		t.Fatal(err)
	}
	for _, id := range []string{quiet, loud} {
		e.exec(`INSERT INTO payments (payment_id, status, user_id, purpose, days) VALUES ($1, 'succeeded', $2, 'subscription', 30)`,
			"pay-"+id, id)
		e.exec(`INSERT INTO payments (payment_id, status, user_id, purpose, days) VALUES ($1, 'pending', $2, 'subscription', 30)`,
			"pending-"+id, id)
	}
	e.pass()
	if got := e.titles(quietEndpoint); len(got) != 0 {
		t.Errorf("default preferences got a payment notice: %v", got)
	}
	if got := e.titles(loudEndpoint); len(got) != 1 || got[0] != "Оплата прошла" {
		t.Errorf("opted in: %v", got)
	}
}

func TestGoneBrowsersAreDroppedAndFailuresRetried(t *testing.T) {
	e := newEnv(t)
	id, gone := e.customer(60 * time.Hour)
	ctx := context.Background()

	e.sender.fail[gone] = webpush.ErrGone
	e.pass()
	subs, _ := e.store.PushSubscriptions(ctx, id)
	if len(subs) != 0 {
		t.Errorf("a gone browser is still stored: %+v", subs)
	}

	// A transient failure keeps the event due.
	flaky := "https://fcm.googleapis.com/fcm/send/flaky-" + id
	_ = e.store.SavePushSubscription(ctx, id, flaky, "k", "a")
	e.sender.fail[flaky] = io.ErrUnexpectedEOF
	e.pass()
	delete(e.sender.fail, flaky)
	e.pass()
	if got := e.titles(flaky); len(got) != 1 {
		t.Errorf("after a transient failure: %v", got)
	}
}

func TestABrowserBelongsToTheAccountThatLastRegisteredIt(t *testing.T) {
	e := newEnv(t)
	ctx := context.Background()
	first, endpoint := e.customer(30 * 24 * time.Hour)
	second, _ := e.customer(30 * 24 * time.Hour)
	if err := e.store.SavePushSubscription(ctx, second, endpoint, "k2", "a2"); err != nil {
		t.Fatal(err)
	}
	if subs, _ := e.store.PushSubscriptions(ctx, first); len(subs) != 0 {
		t.Errorf("the first account still has the browser")
	}
	if subs, _ := e.store.PushSubscriptions(ctx, second); len(subs) != 2 {
		t.Errorf("second account: %+v", subs)
	}
}

func TestSubscriptionsPerCustomerAreCapped(t *testing.T) {
	e := newEnv(t)
	ctx := context.Background()
	id, _ := e.customer(30 * 24 * time.Hour)
	for i := 0; i < 15; i++ {
		_ = e.store.SavePushSubscription(ctx, id, "https://fcm.googleapis.com/fcm/send/many-"+id+"-"+string(rune('a'+i)), "k", "a")
	}
	if subs, _ := e.store.PushSubscriptions(ctx, id); len(subs) != 10 {
		t.Errorf("kept %d browsers", len(subs))
	}
}

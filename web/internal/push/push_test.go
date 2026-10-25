package push

import (
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

func TestExpiryTextCountsWhatIsLeft(t *testing.T) {
	now := time.Date(2026, 10, 25, 12, 0, 0, 0, time.UTC)
	cases := map[time.Duration]string{
		71 * time.Hour:   "3 дня",
		47 * time.Hour:   "2 дня",
		23 * time.Hour:   "23 часа",
		5 * time.Hour:    "5 часов",
		21 * time.Hour:   "21 час",
		30 * time.Minute: "меньше часа",
	}
	for left, want := range cases {
		msg, ttl := Compose(store.PushEvent{Kind: "expiry", Ends: now.Add(left)}, now)
		if !strings.Contains(msg.Body, want) {
			t.Errorf("%v left: %q, want %q", left, msg.Body, want)
		}
		if ttl > left+time.Minute {
			t.Errorf("%v left: held for %v, past the point it is true", left, ttl)
		}
		if msg.URL != "/app/plans" {
			t.Errorf("expiry opens %q", msg.URL)
		}
	}
}

func TestSupportTextNamesTheTicketButNotTheAnswer(t *testing.T) {
	msg, _ := Compose(store.PushEvent{Kind: "support", TicketID: 42, Subject: strings.Repeat("я", 100)}, time.Now())
	if !strings.Contains(msg.Body, "#42") || len([]rune(msg.Body)) > 120 {
		t.Errorf("body %q", msg.Body)
	}
	if msg.Tag != "support-42" || msg.URL != "/app/support" {
		t.Errorf("%+v", msg)
	}
}

func TestPaymentTextFollowsThePurpose(t *testing.T) {
	for purpose, want := range map[string]string{
		"subscription": "продлена на 30 дней",
		"traffic":      "Гигабайты",
		"gift":         "Подарок",
		"":             "Платёж получен",
	} {
		msg, _ := Compose(store.PushEvent{Kind: "payment", Purpose: purpose, Days: 30}, time.Now())
		if !strings.Contains(msg.Body, want) {
			t.Errorf("%q: %q", purpose, msg.Body)
		}
	}
}

func TestEveryNotificationOpensAPageOfThisSite(t *testing.T) {
	// The worker refuses anything else, so a URL that is not a path would be a
	// notification that opens nothing.
	for _, kind := range []string{"expiry", "support", "payment", "unknown"} {
		msg, _ := Compose(store.PushEvent{Kind: kind, Ends: time.Now().Add(time.Hour)}, time.Now())
		if !strings.HasPrefix(msg.URL, "/") || strings.HasPrefix(msg.URL, "//") {
			t.Errorf("%s opens %q", kind, msg.URL)
		}
	}
}

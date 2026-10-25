// Package push decides what a customer is told by Web Push, and sends it.
//
// It reads Postgres for what is due -- a subscription about to run out, an
// operator's answer, a credited payment -- the same way admin_bot reads the
// support outbox: nothing calls into it, so the Python webhook and admin_bot
// need no idea it exists.
package push

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/webpush"
)

// Interval between passes. Expiry is measured in days and support answers in
// minutes; a minute is quick enough for both and nothing for the database.
const Interval = time.Minute

// sentRetention outlives every look-back window in store.pendingPushEvents.
const sentRetention = 30 * 24 * time.Hour

type sender interface {
	Send(ctx context.Context, sub webpush.Subscription, msg webpush.Message, ttl time.Duration) error
}

type Service struct {
	store     *store.Store
	sender    sender
	PublicKey string
	log       *slog.Logger
}

func New(st *store.Store, keys *webpush.Keys, subject string, log *slog.Logger) *Service {
	return &Service{store: st, sender: webpush.NewSender(keys, subject), PublicKey: keys.Public, log: log}
}

// Run sends what is due every Interval until ctx ends.
func (s *Service) Run(ctx context.Context) {
	ticker := time.NewTicker(Interval)
	defer ticker.Stop()
	lastPrune := time.Time{}
	for {
		if err := s.pass(ctx); err != nil && ctx.Err() == nil {
			s.log.Error("push pass", "err", err)
		}
		if time.Since(lastPrune) > 24*time.Hour {
			if n, err := s.store.PruneSentPushEvents(ctx, sentRetention); err != nil {
				s.log.Error("prune push_sent", "err", err)
			} else {
				lastPrune = time.Now()
				if n > 0 {
					s.log.Info("pruned push_sent", "rows", n)
				}
			}
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func (s *Service) pass(ctx context.Context) error {
	events, err := s.store.PendingPushEvents(ctx)
	if err != nil {
		return err
	}
	for _, event := range events {
		claimed, err := s.store.ClaimPushEvent(ctx, event.UserID, event.Key)
		if err != nil {
			return err
		}
		if !claimed {
			continue
		}
		msg, ttl := Compose(event, time.Now())
		delivered, err := s.SendToUser(ctx, event.UserID, msg, ttl)
		if err != nil {
			s.log.Warn("push not delivered", "event", event.Key, "err", err)
		}
		if delivered == 0 {
			// Nothing took it: try again next pass, while the event is still
			// inside its window.
			if err := s.store.ReleasePushEvent(ctx, event.UserID, event.Key); err != nil {
				return err
			}
		}
	}
	return nil
}

// SendToUser delivers to every browser the customer has, and returns how many
// accepted it. Browsers the push service has forgotten are deleted.
func (s *Service) SendToUser(ctx context.Context, userID string, msg webpush.Message, ttl time.Duration) (int, error) {
	subs, err := s.store.PushSubscriptions(ctx, userID)
	if err != nil {
		return 0, err
	}
	delivered := 0
	var lastErr error
	for _, sub := range subs {
		err := s.sender.Send(ctx, webpush.Subscription{Endpoint: sub.Endpoint, P256dh: sub.P256dh, Auth: sub.Auth}, msg, ttl)
		switch {
		case err == nil:
			delivered++
		case errors.Is(err, webpush.ErrGone):
			if err := s.store.DeletePushSubscriptionByID(ctx, sub.ID); err != nil {
				lastErr = err
			}
		default:
			lastErr = err
		}
	}
	return delivered, lastErr
}

// Compose writes the notification for an event. The text says what happened
// and nothing private: it shows on a lock screen, and an answer's content
// belongs in the cabinet, behind the sign-in.
func Compose(event store.PushEvent, now time.Time) (webpush.Message, time.Duration) {
	switch event.Kind {
	case "expiry":
		left := event.Ends.Sub(now)
		body := "Подписка закончится через " + humanDays(left) + ". Продлите, чтобы VPN не отключился."
		// Held no longer than it stays true.
		return webpush.Message{
			Title: "Подписка заканчивается",
			Body:  body,
			URL:   "/app/plans",
			Tag:   "expiry",
		}, clampTTL(left)
	case "support":
		return webpush.Message{
			Title: "Ответ поддержки",
			Body:  fmt.Sprintf("По обращению #%d «%s» пришёл ответ.", event.TicketID, truncate(event.Subject, 60)),
			URL:   "/app/support",
			Tag:   fmt.Sprintf("support-%d", event.TicketID),
		}, 3 * 24 * time.Hour
	case "payment":
		body := "Платёж получен."
		switch event.Purpose {
		case "subscription":
			if event.Days > 0 {
				body = fmt.Sprintf("Подписка продлена на %d %s.", event.Days, daysWord(event.Days))
			} else {
				body = "Подписка продлена."
			}
		case "traffic":
			body = "Гигабайты начислены."
		case "gift":
			body = "Подарок оплачен, код — в разделе «Тарифы»."
		}
		return webpush.Message{Title: "Оплата прошла", Body: body, URL: "/app", Tag: "payment"}, 24 * time.Hour
	}
	return webpush.Message{Title: "KairaVPN", URL: "/app"}, time.Hour
}

func clampTTL(d time.Duration) time.Duration {
	if d < time.Minute {
		return time.Minute
	}
	return d
}

func humanDays(d time.Duration) string {
	if d < 24*time.Hour {
		hours := int(d.Hours())
		if hours < 1 {
			return "меньше часа"
		}
		return fmt.Sprintf("%d %s", hours, plural(hours, "час", "часа", "часов"))
	}
	days := int((d + 12*time.Hour) / (24 * time.Hour))
	return fmt.Sprintf("%d %s", days, daysWord(days))
}

func daysWord(n int) string { return plural(n, "день", "дня", "дней") }

func plural(n int, one, few, many string) string {
	n100 := n % 100
	n10 := n % 10
	switch {
	case n100 >= 11 && n100 <= 14:
		return many
	case n10 == 1:
		return one
	case n10 >= 2 && n10 <= 4:
		return few
	}
	return many
}

func truncate(s string, max int) string {
	runes := []rune(s)
	if len(runes) <= max {
		return s
	}
	return string(runes[:max-1]) + "…"
}

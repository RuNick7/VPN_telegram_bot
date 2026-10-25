package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// Web Push: which browsers a customer allowed, what they want to hear about,
// and what has already been sent. Only the website touches these tables.

// maxPushSubscriptions per customer. A phone, a laptop, a work machine and a
// few reinstalls; past that the oldest goes, so a script cannot make every
// event fan out to thousands of endpoints.
const maxPushSubscriptions = 10

type PushSubscription struct {
	ID       int64
	Endpoint string
	P256dh   string
	Auth     string
}

// PushPreferences are the customer's choices. The zero row is not the
// default; DefaultPushPreferences is.
type PushPreferences struct {
	Expiry  bool `json:"expiry"`
	Support bool `json:"support"`
	Payment bool `json:"payment"`
}

// DefaultPushPreferences: the important things only. Must match the column
// defaults in migrations/0017_web_push.
var DefaultPushPreferences = PushPreferences{Expiry: true, Support: true, Payment: false}

// SavePushSubscription records a browser for this customer, or moves it here
// from whoever had it before -- the endpoint is the browser, not the account.
func (s *Store) SavePushSubscription(ctx context.Context, userID, endpoint, p256dh, auth string) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx,
		`INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
		 VALUES ($1, $2, $3, $4)
		 ON CONFLICT (endpoint) DO UPDATE
		 SET user_id = EXCLUDED.user_id, p256dh = EXCLUDED.p256dh,
		     auth = EXCLUDED.auth, seen_at = now()`,
		userID, endpoint, p256dh, auth); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx,
		`DELETE FROM push_subscriptions
		 WHERE user_id = $1 AND id NOT IN (
		     SELECT id FROM push_subscriptions WHERE user_id = $1
		     ORDER BY seen_at DESC, id DESC LIMIT $2)`,
		userID, maxPushSubscriptions); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// DeletePushSubscription forgets one of this customer's browsers. Someone
// else's endpoint is simply not found.
func (s *Store) DeletePushSubscription(ctx context.Context, userID, endpoint string) error {
	_, err := s.pool.Exec(ctx,
		`DELETE FROM push_subscriptions WHERE user_id = $1 AND endpoint = $2`, userID, endpoint)
	return err
}

// DeletePushSubscriptionByID drops a browser the push service says is gone.
func (s *Store) DeletePushSubscriptionByID(ctx context.Context, id int64) error {
	_, err := s.pool.Exec(ctx, `DELETE FROM push_subscriptions WHERE id = $1`, id)
	return err
}

func (s *Store) PushSubscriptions(ctx context.Context, userID string) ([]PushSubscription, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = $1 ORDER BY id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var subs []PushSubscription
	for rows.Next() {
		var sub PushSubscription
		if err := rows.Scan(&sub.ID, &sub.Endpoint, &sub.P256dh, &sub.Auth); err != nil {
			return nil, err
		}
		subs = append(subs, sub)
	}
	return subs, rows.Err()
}

func (s *Store) PushPreferences(ctx context.Context, userID string) (PushPreferences, error) {
	prefs := DefaultPushPreferences
	err := s.pool.QueryRow(ctx,
		`SELECT expiry, support, payment FROM push_preferences WHERE user_id = $1`, userID).
		Scan(&prefs.Expiry, &prefs.Support, &prefs.Payment)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return DefaultPushPreferences, err
	}
	return prefs, nil
}

func (s *Store) SetPushPreferences(ctx context.Context, userID string, prefs PushPreferences) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO push_preferences (user_id, expiry, support, payment)
		 VALUES ($1, $2, $3, $4)
		 ON CONFLICT (user_id) DO UPDATE
		 SET expiry = EXCLUDED.expiry, support = EXCLUDED.support,
		     payment = EXCLUDED.payment, updated_at = now()`,
		userID, prefs.Expiry, prefs.Support, prefs.Payment)
	return err
}

// PushEvent is something a customer should be told, not yet sent.
type PushEvent struct {
	UserID string
	Key    string // the push_sent key; also says which kind it is
	Kind   string // expiry | support | payment

	// expiry
	Ends time.Time
	// support
	TicketID int64
	Subject  string
	// payment
	Purpose string
	Days    int
}

// pendingPushEvents finds everything due, for customers who have at least one
// browser and want that kind of event. Each part looks back a bounded window,
// so a customer who turns notifications on is not told about last month.
const pendingPushEvents = `
WITH reachable AS (
    SELECT DISTINCT s.user_id, COALESCE(p.expiry, TRUE) AS expiry,
           COALESCE(p.support, TRUE) AS support, COALESCE(p.payment, FALSE) AS payment
    FROM push_subscriptions s
    LEFT JOIN push_preferences p ON p.user_id = s.user_id
),
due AS (
    -- Three days out, then one: two reminders per period. The end date is in
    -- the key, so renewing starts the count again.
    SELECT u.id AS user_id, 'expiry' AS kind,
           'expiry:' || EXTRACT(EPOCH FROM u.subscription_ends)::bigint || ':' ||
               CASE WHEN u.subscription_ends <= now() + interval '1 day' THEN '1' ELSE '3' END AS event_key,
           u.subscription_ends AS ends, 0::bigint AS ticket_id, '' AS subject, '' AS purpose, 0 AS days
    FROM users u JOIN reachable r ON r.user_id = u.id AND r.expiry
    WHERE u.merged_into IS NULL
      AND u.subscription_ends > now()
      AND u.subscription_ends <= now() + interval '3 days'

    UNION ALL

    -- An operator's answer the customer has not opened yet.
    SELECT t.user_id, 'support', 'support:' || m.id,
           to_timestamp(0), t.id, t.subject, '', 0
    FROM support_messages m
    JOIN support_tickets t ON t.id = m.ticket_id
    JOIN reachable r ON r.user_id = t.user_id AND r.support
    WHERE m.author = 'admin'
      AND m.created_at > now() - interval '1 day'
      AND m.created_at > t.user_read_at

    UNION ALL

    -- A payment the webhook has credited. Only the site's own payments carry
    -- a user_id; the bot reports its payments in its chat.
    SELECT pay.user_id, 'payment', 'payment:' || pay.payment_id,
           to_timestamp(0), 0, '', pay.purpose, pay.days
    FROM payments pay
    JOIN reachable r ON r.user_id = pay.user_id AND r.payment
    WHERE pay.status = 'succeeded'
      AND pay.updated_at > now() - interval '1 day'
)
SELECT d.user_id, d.kind, d.event_key, d.ends, d.ticket_id, d.subject, d.purpose, d.days
FROM due d
WHERE NOT EXISTS (
    SELECT 1 FROM push_sent ps WHERE ps.user_id = d.user_id AND ps.event_key = d.event_key)
ORDER BY d.user_id
LIMIT 500`

func (s *Store) PendingPushEvents(ctx context.Context) ([]PushEvent, error) {
	rows, err := s.pool.Query(ctx, pendingPushEvents)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var events []PushEvent
	for rows.Next() {
		var e PushEvent
		if err := rows.Scan(&e.UserID, &e.Kind, &e.Key, &e.Ends, &e.TicketID, &e.Subject, &e.Purpose, &e.Days); err != nil {
			return nil, err
		}
		events = append(events, e)
	}
	return events, rows.Err()
}

// ClaimPushEvent marks an event as sent before sending it, and reports
// whether this caller got there first.
func (s *Store) ClaimPushEvent(ctx context.Context, userID, key string) (bool, error) {
	tag, err := s.pool.Exec(ctx,
		`INSERT INTO push_sent (user_id, event_key) VALUES ($1, $2) ON CONFLICT DO NOTHING`,
		userID, key)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// ReleasePushEvent undoes a claim when no browser took the message, so the
// next pass tries again.
func (s *Store) ReleasePushEvent(ctx context.Context, userID, key string) error {
	_, err := s.pool.Exec(ctx, `DELETE FROM push_sent WHERE user_id = $1 AND event_key = $2`, userID, key)
	return err
}

// PruneSentPushEvents drops records older than any window above looks back.
func (s *Store) PruneSentPushEvents(ctx context.Context, olderThan time.Duration) (int64, error) {
	tag, err := s.pool.Exec(ctx,
		`DELETE FROM push_sent WHERE sent_at < now() - make_interval(secs => $1)`, olderThan.Seconds())
	if err != nil {
		return 0, err
	}
	return tag.RowsAffected(), nil
}

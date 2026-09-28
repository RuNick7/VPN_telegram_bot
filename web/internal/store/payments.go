package store

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
)

// Payment state is owned by the Python webhook handler, not by this service.
//
// The site creates payments at YooKassa and records them as pending so the
// user can be shown "waiting for payment". Deciding that a payment *succeeded*
// requires verifying it against YooKassa server-to-server, because the webhook
// callback carries no signature of its own -- trusting its body was a shipped,
// exploitable forgery hole, fixed in Phase 0 and guarded by tests on the
// Python side.
//
// Rather than reimplement that verification here and have two services racing
// to credit the same payment, this package exposes no way to change a
// payment's status at all. Postgres is the integration point; the rule is
// enforced by absence.

// InsertPendingPayment records a payment the site just created at YooKassa,
// along with whose it is and what it was for.
//
// The status column is still untouchable -- ON CONFLICT leaves it exactly as
// found, so a retry of our own request cannot reset something the webhook has
// since written. The other three columns are new and are the reason this is
// worth writing at all: a payment stuck in `processing_error` used to be a
// bare id, and working out who had paid meant reading the YooKassa dashboard
// and matching timestamps by hand.
func (s *Store) InsertPendingPayment(ctx context.Context, paymentID, userID, purpose string, days int) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO payments (payment_id, status, user_id, purpose, days)
		 VALUES ($1, 'pending', $2, $3, $4)
		 ON CONFLICT (payment_id) DO UPDATE
		 SET user_id = COALESCE(payments.user_id, EXCLUDED.user_id),
		     purpose = CASE WHEN payments.purpose = '' THEN EXCLUDED.purpose ELSE payments.purpose END,
		     days    = CASE WHEN payments.days = 0 THEN EXCLUDED.days ELSE payments.days END`,
		paymentID, userID, purpose, days)
	return err
}

// PaymentStatus reads what the webhook has recorded, for polling a payment
// from the browser after the user returns from YooKassa.
// PaymentStatus reports the status of one of this user's payments.
//
// Scoped to the caller. It used to take the id alone, so any signed-in visitor
// could read the state of any payment whose id they had -- an id that travels
// in URLs, in YooKassa's own emails and in logs.
//
// Only the site's own payments are readable here, and every one of them is
// stamped with a user by InsertPendingPayment. Rows the bot wrote carry no
// user_id and are deliberately invisible: the bot reports its own payments in
// the chat that started them.
func (s *Store) PaymentStatus(ctx context.Context, paymentID, userID string) (string, error) {
	var status string
	err := s.pool.QueryRow(ctx,
		`SELECT status FROM payments WHERE payment_id = $1 AND user_id = $2`,
		paymentID, userID).Scan(&status)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", ErrNotFound
	}
	return status, err
}

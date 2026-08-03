package store

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// Binding a confirmed address to an account that already exists.
//
// Not the same thing as a magic link, and the difference is why these are a
// separate table. A magic link is keyed by *address* and signs somebody in; it
// reveals nothing about whether that address has an account, which is why the
// account is only resolved at redemption. These are keyed by *user*: the
// account is already known, and what the token proves is that whoever is
// driving it also controls the mailbox.
//
// The bot mints these too (shared/tgvpn_shared/db/email_verifications.py) and
// posts its own letter, but the link always lands here. Redemption lives on
// this side alone, because confirming also pays the link bonus and writes the
// address -- rules that must have exactly one implementation.

// CreateEmailVerification issues a token, replacing any this user still had
// outstanding.
//
// Replacing rather than accumulating: somebody who mistypes their address and
// asks again should not leave a live token pointing at the typo, and the
// newest request is the only one they are looking at.
func (s *Store) CreateEmailVerification(ctx context.Context, token, userID, email string, ttl time.Duration) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx,
		`DELETE FROM email_verifications WHERE user_id = $1 AND consumed_at IS NULL`,
		userID); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO email_verifications (token_hash, user_id, email, expires_at)
		 VALUES ($1, $2, lower($3), now() + $4::interval)`,
		HashToken(token), userID, strings.TrimSpace(email), ttl.String()); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// EmailVerification is what a redeemed token was issued for.
type EmailVerification struct {
	UserID string
	Email  string
}

// ConsumeEmailVerification redeems a confirmation token.
//
// The `consumed_at IS NULL` guard is inside the UPDATE so redemption is
// atomic: a link a mail client prefetched, or one opened twice, can only bind
// an address once. A second attempt matches no row and is indistinguishable
// from an invalid token, which is what the caller should say anyway.
func (s *Store) ConsumeEmailVerification(ctx context.Context, token string) (*EmailVerification, error) {
	var v EmailVerification
	err := s.pool.QueryRow(ctx,
		`UPDATE email_verifications SET consumed_at = now()
		 WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
		 RETURNING user_id, email`,
		HashToken(token)).Scan(&v.UserID, &v.Email)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &v, nil
}

// SetConfirmedEmail writes an address that has just been proved.
//
// Refuses when somebody else already holds it rather than taking it: the
// address is a sign-in route, and moving one between accounts on the strength
// of a confirmation would let a person who controls a mailbox pull an account
// somebody else built onto it.
//
// It never merges either. Two real accounts turning out to be one person is
// what the Telegram link handshake is for, and that is a decision the customer
// makes deliberately -- not a side effect of opening a letter.
func (s *Store) SetConfirmedEmail(ctx context.Context, userID, email string) (bool, error) {
	cmd, err := s.pool.Exec(ctx,
		`UPDATE users SET email = lower($1)
		 WHERE id = $2
		   AND NOT EXISTS (
		       SELECT 1 FROM users other
		       WHERE lower(other.email) = lower($1) AND other.id <> $2
		   )`,
		strings.TrimSpace(email), userID)
	if err != nil {
		return false, err
	}
	return cmd.RowsAffected() > 0, nil
}

func (s *Store) DeleteExpiredEmailVerifications(ctx context.Context) (int64, error) {
	cmd, err := s.pool.Exec(ctx,
		`DELETE FROM email_verifications WHERE expires_at < now() - interval '1 day'`)
	if err != nil {
		return 0, err
	}
	return cmd.RowsAffected(), nil
}

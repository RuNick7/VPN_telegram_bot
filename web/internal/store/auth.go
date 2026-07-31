package store

import (
	"context"
	"crypto/sha256"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// HashToken reduces a secret to what we are willing to store.
//
// Sessions and magic links are both kept only as digests, so a dump of this
// database yields no working credential. SHA-256 without a salt is the right
// call here and not a shortcut: these are 256-bit random tokens, not
// user-chosen passwords, so there is no dictionary to attack and nothing a
// slow KDF would buy.
func HashToken(token string) []byte {
	sum := sha256.Sum256([]byte(token))
	return sum[:]
}

// -- sessions ---------------------------------------------------------------

func (s *Store) CreateSession(ctx context.Context, token, userID string, ttl time.Duration, userAgent, ip string) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO web_sessions (token_hash, user_id, expires_at, user_agent, ip)
		 VALUES ($1, $2, now() + $3::interval, $4, $5)`,
		HashToken(token), userID, ttl.String(), truncate(userAgent, 300), ip)
	return err
}

// SessionUser resolves a session token to its user, refreshing last_seen_at.
//
// Expiry is checked in the statement rather than after the read: a session
// that lapsed a second ago must not authenticate a request just because the
// row is still there waiting to be swept.
func (s *Store) SessionUser(ctx context.Context, token string) (*User, error) {
	var userID string
	err := s.pool.QueryRow(ctx,
		`UPDATE web_sessions SET last_seen_at = now()
		 WHERE token_hash = $1 AND expires_at > now()
		 RETURNING user_id`,
		HashToken(token)).Scan(&userID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return s.UserByID(ctx, userID)
}

func (s *Store) DeleteSession(ctx context.Context, token string) error {
	_, err := s.pool.Exec(ctx, `DELETE FROM web_sessions WHERE token_hash = $1`, HashToken(token))
	return err
}

// DeleteExpiredSessions sweeps lapsed rows. Purely housekeeping -- nothing
// depends on it having run, because SessionUser filters on expiry itself.
func (s *Store) DeleteExpiredSessions(ctx context.Context) (int64, error) {
	cmd, err := s.pool.Exec(ctx, `DELETE FROM web_sessions WHERE expires_at < now()`)
	if err != nil {
		return 0, err
	}
	return cmd.RowsAffected(), nil
}

// -- magic links ------------------------------------------------------------

func (s *Store) CreateMagicLink(ctx context.Context, token, email string, ttl time.Duration) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO magic_link_tokens (token_hash, email, expires_at)
		 VALUES ($1, lower($2), now() + $3::interval)`,
		HashToken(token), strings.TrimSpace(email), ttl.String())
	return err
}

// ConsumeMagicLink redeems a login link and returns the address it was issued
// for.
//
// The `consumed_at IS NULL` guard lives in the UPDATE so redemption is atomic:
// a link forwarded to someone else, or simply loaded twice by a mail client
// that prefetches URLs, can only ever produce one session. A second attempt
// finds no row and is indistinguishable from an invalid token, which is what
// we want to tell the caller anyway.
func (s *Store) ConsumeMagicLink(ctx context.Context, token string) (string, error) {
	var email string
	err := s.pool.QueryRow(ctx,
		`UPDATE magic_link_tokens SET consumed_at = now()
		 WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
		 RETURNING email`,
		HashToken(token)).Scan(&email)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", ErrNotFound
	}
	return email, err
}

func (s *Store) DeleteExpiredMagicLinks(ctx context.Context) (int64, error) {
	cmd, err := s.pool.Exec(ctx,
		`DELETE FROM magic_link_tokens WHERE expires_at < now() - interval '1 day'`)
	if err != nil {
		return 0, err
	}
	return cmd.RowsAffected(), nil
}

// -- rate limiting ----------------------------------------------------------

// AllowAttempt counts one attempt against a bucket and reports whether it is
// within the limit.
//
// The whole thing is one statement so concurrent requests cannot both read a
// count below the limit and then both write. `window_starts` doubles as the
// reset marker: once the window has elapsed the row is reset to a single
// attempt rather than deleted, which avoids a delete/insert race.
func (s *Store) AllowAttempt(ctx context.Context, bucket string, limit int, window time.Duration) (bool, error) {
	var attempts int
	err := s.pool.QueryRow(ctx,
		`INSERT INTO auth_rate_limits (bucket, attempts, window_starts)
		 VALUES ($1, 1, now())
		 ON CONFLICT (bucket) DO UPDATE SET
		     attempts = CASE
		         WHEN auth_rate_limits.window_starts < now() - $2::interval THEN 1
		         ELSE auth_rate_limits.attempts + 1
		     END,
		     window_starts = CASE
		         WHEN auth_rate_limits.window_starts < now() - $2::interval THEN now()
		         ELSE auth_rate_limits.window_starts
		     END
		 RETURNING attempts`,
		bucket, window.String()).Scan(&attempts)
	if err != nil {
		return false, err
	}
	return attempts <= limit, nil
}

func truncate(value string, max int) string {
	if len(value) <= max {
		return value
	}
	return value[:max]
}

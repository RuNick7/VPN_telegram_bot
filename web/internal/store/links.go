package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// Account-link tokens are the website half of attaching a Telegram account.
//
// The site mints one and shows the user a t.me link carrying it; the bot
// redeems it. Stored hashed, like sessions and magic links, so the plaintext
// exists only in the link the user was handed.

func (s *Store) CreateLinkToken(ctx context.Context, token, userID string, ttl time.Duration) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO account_link_tokens (token_hash, user_id, expires_at)
		 VALUES ($1, $2, now() + $3::interval)`,
		HashToken(token), userID, ttl.String())
	return err
}

// UserByIDFollowingMerge resolves an internal id to the account that is
// actually live.
//
// A merged account's id stays valid on purpose: a browser session, a payment
// in flight at YooKassa, or a link handed out yesterday all carry the old id,
// and each has to land on the surviving account rather than on a dead row.
// The walk is bounded because a merge only ever points at a row that is not
// itself merged.
func (s *Store) UserByIDFollowingMerge(ctx context.Context, id string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`WITH RECURSIVE chain AS (
			SELECT id, merged_into, 0 AS depth FROM users WHERE id = $1
			UNION ALL
			SELECT u.id, u.merged_into, chain.depth + 1
			FROM users u JOIN chain ON u.id = chain.merged_into
			WHERE chain.depth < 8
		)
		SELECT `+userColumns+` FROM users
		WHERE id = (SELECT id FROM chain WHERE merged_into IS NULL LIMIT 1)`,
		id))
}

// PendingLinkToken reports whether a user already has a live, unredeemed link
// token, so the UI can show the same link again instead of minting a new one
// every time the page is opened.
func (s *Store) HasPendingLinkToken(ctx context.Context, userID string) (bool, error) {
	var exists bool
	err := s.pool.QueryRow(ctx,
		`SELECT EXISTS (
			SELECT 1 FROM account_link_tokens
			WHERE user_id = $1 AND consumed_at IS NULL AND expires_at > now()
		 )`, userID).Scan(&exists)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return exists, err
}

func (s *Store) DeleteExpiredLinkTokens(ctx context.Context) (int64, error) {
	cmd, err := s.pool.Exec(ctx,
		`DELETE FROM account_link_tokens WHERE expires_at < now() - interval '1 day'`)
	if err != nil {
		return 0, err
	}
	return cmd.RowsAffected(), nil
}

// SetPanelIdentity records which panel account belongs to a user.
//
// Written both when we create one and when a lookup by a legacy name
// succeeds; backfilling on read is what retires the legacy path one user at a
// time, without a bulk rename against a live panel.
func (s *Store) SetPanelIdentity(ctx context.Context, userID, panelUUID, panelUsername string) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE users SET remnawave_uuid = $1::uuid, remnawave_username = $2 WHERE id = $3`,
		panelUUID, panelUsername, userID)
	return err
}

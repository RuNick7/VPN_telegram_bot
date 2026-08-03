package store

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

type Promo struct {
	Code     string
	Type     string // "days" | "gift"
	Value    int
	IsActive bool
	OneTime  bool
	// Who bought it, by both handles. CreatorID is a Telegram ID and is absent
	// for anything bought on the site; CreatorUserID is the internal id every
	// account has, and is what the "you cannot redeem your own gift" check has
	// to compare -- on Telegram IDs alone, a website buyer could activate the
	// gift they had just paid for.
	CreatorID     *int64
	CreatorUserID *string
}

func (s *Store) PromoByCode(ctx context.Context, code string) (*Promo, error) {
	var p Promo
	err := s.pool.QueryRow(ctx,
		`SELECT code, type, value, is_active, one_time, creator_id, creator_user_id
		 FROM promo_codes WHERE code = $1`,
		strings.ToUpper(strings.TrimSpace(code)),
	).Scan(&p.Code, &p.Type, &p.Value, &p.IsActive, &p.OneTime, &p.CreatorID, &p.CreatorUserID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &p, err
}

// Gift is one code a customer bought, and whether anyone has used it yet.
type Gift struct {
	Code       string
	Days       int
	CreatedAt  time.Time
	RedeemedAt *time.Time
}

// GiftsCreatedBy lists the gifts this account has paid for, newest first.
//
// This is the whole reason `creator_user_id` exists. A gift is handed over as
// a Telegram message, and a buyer who has no Telegram account received
// nothing at all: the code was generated, charged for, and reachable from
// nowhere. Now it is on the page they are returned to after paying.
//
// Redemption is read from `promo_usage` rather than stored on the code,
// because that table is what the claim actually writes -- a second copy of
// "has this been used" could disagree with the one the redemption path
// enforces.
func (s *Store) GiftsCreatedBy(ctx context.Context, userID string) ([]Gift, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT p.code, p.value, p.created_at,
		        (SELECT min(u.used_at) FROM promo_usage u WHERE u.code = p.code)
		 FROM promo_codes p
		 WHERE p.creator_user_id = $1 AND p.type = 'gift'
		 ORDER BY p.created_at DESC`,
		userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	gifts := []Gift{}
	for rows.Next() {
		var g Gift
		if err := rows.Scan(&g.Code, &g.Days, &g.CreatedAt, &g.RedeemedAt); err != nil {
			return nil, err
		}
		gifts = append(gifts, g)
	}
	return gifts, rows.Err()
}

// ClaimPromo reserves a code for a user before anything is credited.
//
// Claiming first and crediting second is what stops two people redeeming a
// one-time code simultaneously: the loser's insert finds the code already
// taken. If crediting then fails, ReleasePromo puts it back -- the same
// semantics as the Python PromoRepository, so a code behaves identically
// whether it is redeemed in the bot or on the site.
//
// Keyed on `users.id`, which every account has. It used to be keyed on
// telegram_id, and that made gifts useless to exactly the people most likely
// to receive one: somebody handed a gift link who has never used Telegram.
//
// `telegramID` is stored when we have one and is nil-safe otherwise; nothing
// keys on it, it is there so support can recognise the row.
func (s *Store) ClaimPromo(ctx context.Context, code, userID string, telegramID *int64, oneTime bool) (bool, error) {
	code = strings.ToUpper(strings.TrimSpace(code))

	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx)

	var taken bool
	if oneTime {
		err = tx.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM promo_usage WHERE code = $1)`, code).Scan(&taken)
	} else {
		err = tx.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM promo_usage WHERE code = $1 AND user_id = $2)`,
			code, userID).Scan(&taken)
	}
	if err != nil {
		return false, err
	}
	if taken {
		return false, tx.Commit(ctx)
	}

	if _, err := tx.Exec(ctx,
		`INSERT INTO promo_usage (code, telegram_id, user_id) VALUES ($1, $2, $3)`,
		code, telegramID, userID); err != nil {
		return false, err
	}
	return true, tx.Commit(ctx)
}

// ReleasePromo undoes a claim whose crediting failed, so the user can retry.
func (s *Store) ReleasePromo(ctx context.Context, code, userID string) error {
	_, err := s.pool.Exec(ctx,
		`DELETE FROM promo_usage WHERE code = $1 AND user_id = $2`,
		strings.ToUpper(strings.TrimSpace(code)), userID)
	return err
}

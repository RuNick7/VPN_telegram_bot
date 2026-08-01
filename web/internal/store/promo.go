package store

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
)

type Promo struct {
	Code      string
	Type      string // "days" | "gift"
	Value     int
	IsActive  bool
	OneTime   bool
	CreatorID *int64
}

func (s *Store) PromoByCode(ctx context.Context, code string) (*Promo, error) {
	var p Promo
	err := s.pool.QueryRow(ctx,
		`SELECT code, type, value, is_active, one_time, creator_id
		 FROM promo_codes WHERE code = $1`,
		strings.ToUpper(strings.TrimSpace(code)),
	).Scan(&p.Code, &p.Type, &p.Value, &p.IsActive, &p.OneTime, &p.CreatorID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &p, err
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

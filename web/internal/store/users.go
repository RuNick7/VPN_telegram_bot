package store

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var ErrNotFound = errors.New("not found")

// User is the subset of the `users` row the website reads.
//
// TelegramID is nullable: the schema has allowed a person to exist without one
// since the first migration, and an account created by email on the site is
// exactly that case.
type User struct {
	ID               string
	TelegramID       *int64
	TelegramTag      string
	Email            string
	SubscriptionEnds time.Time
	ReferrerTag      string
	ReferredPeople   int
	GiftedSubs       int
	CreatedAt        time.Time

	LTEPaidBalanceBytes int64
	LTECycleStart       *time.Time
	LTELastUsageBytes   int64
	LTEFreeGBOverride   *int
	SquadTier           string
}

// SubscriptionActive reports whether the paid period is still running.
func (u *User) SubscriptionActive() bool { return u.SubscriptionEnds.After(time.Now()) }

const userColumns = `
	id, telegram_id, telegram_tag, COALESCE(email, ''), subscription_ends,
	COALESCE(referrer_tag, ''), referred_people, gifted_subscriptions, created_at,
	lte_paid_balance_bytes, lte_cycle_start, lte_last_usage_bytes,
	lte_free_gb_override, squad_tier
`

func scanUser(row pgx.Row) (*User, error) {
	var u User
	err := row.Scan(
		&u.ID, &u.TelegramID, &u.TelegramTag, &u.Email, &u.SubscriptionEnds,
		&u.ReferrerTag, &u.ReferredPeople, &u.GiftedSubs, &u.CreatedAt,
		&u.LTEPaidBalanceBytes, &u.LTECycleStart, &u.LTELastUsageBytes,
		&u.LTEFreeGBOverride, &u.SquadTier,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &u, nil
}

func (s *Store) UserByID(ctx context.Context, id string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE id = $1`, id))
}

// UserByEmail looks a user up case-insensitively.
//
// Addresses are stored as the user typed them, but nobody expects
// Bob@example.com and bob@example.com to be different accounts -- and treating
// them as different would let one person hold two accounts on one mailbox.
func (s *Store) UserByEmail(ctx context.Context, email string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE lower(email) = lower($1)`, strings.TrimSpace(email)))
}

func (s *Store) UserByTelegramID(ctx context.Context, telegramID int64) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE telegram_id = $1`, telegramID))
}

func (s *Store) UserByTag(ctx context.Context, tag string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE lower(telegram_tag) = lower($1)`, strings.TrimSpace(tag)))
}

// CreateEmailUser registers someone who arrived through the website with no
// Telegram account at all.
//
// `telegram_id` stays NULL, which the schema has always permitted. Such a user
// has no bot-side presence: the bot addresses people by telegram_id and simply
// will not find them, which is correct -- they have never spoken to it.
// Linking a Telegram account onto an existing email account afterwards is the
// account-merge half of the identity rework, and is not attempted here.
func (s *Store) CreateEmailUser(ctx context.Context, email string) (*User, error) {
	var id string
	err := s.pool.QueryRow(ctx,
		`INSERT INTO users (email, subscription_ends, created_at)
		 VALUES ($1, to_timestamp(0), now())
		 RETURNING id`,
		strings.TrimSpace(email),
	).Scan(&id)
	if err != nil {
		return nil, err
	}
	return s.UserByID(ctx, id)
}

func (s *Store) SetEmail(ctx context.Context, userID, email string) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE users SET email = $1 WHERE id = $2`, strings.TrimSpace(email), userID)
	return err
}

// SetReferrerTag records who invited this user, once and only once.
//
// The "referrer already set" guard lives in the statement itself
// rather than in a read-then-write around it: two requests racing each other
// would otherwise both see "not set yet" and the second would overwrite the
// first. Returns false when a referrer was already recorded.
func (s *Store) SetReferrerTag(ctx context.Context, userID, tag string) (bool, error) {
	cmd, err := s.pool.Exec(ctx,
		`UPDATE users SET referrer_tag = $1
		 WHERE id = $2 AND (referrer_tag IS NULL OR referrer_tag = '')`,
		strings.TrimSpace(tag), userID)
	if err != nil {
		return false, err
	}
	return cmd.RowsAffected() > 0, nil
}

// AwardReferral credits the referrer with one invitee, at most once ever.
//
// Mirrors UserRepository.award_referral on the Python side, including its
// atomicity: the increment and the `is_referred` flag move together in one
// statement, so a retry cannot credit the same person twice.
func (s *Store) AwardReferral(ctx context.Context, referrerTag string, inviteeID string) (bool, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx)

	var alreadyReferred bool
	err = tx.QueryRow(ctx,
		`SELECT is_referred FROM users WHERE id = $1 FOR UPDATE`, inviteeID).Scan(&alreadyReferred)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, ErrNotFound
	}
	if err != nil {
		return false, err
	}
	if alreadyReferred {
		return false, tx.Commit(ctx)
	}

	cmd, err := tx.Exec(ctx,
		`UPDATE users SET referred_people = referred_people + 1
		 WHERE lower(telegram_tag) = lower($1)`, strings.TrimSpace(referrerTag))
	if err != nil {
		return false, err
	}
	if cmd.RowsAffected() == 0 {
		return false, tx.Commit(ctx) // no such referrer; nothing credited
	}

	if _, err := tx.Exec(ctx,
		`UPDATE users SET is_referred = TRUE WHERE id = $1`, inviteeID); err != nil {
		return false, err
	}
	return true, tx.Commit(ctx)
}

// ExtendSubscription pushes the expiry out by `days`, from whichever is later:
// the current expiry or now.
//
// Extending from `now` when a subscription has already lapsed is what stops a
// renewal from being back-dated into a period the user never had. Returns the
// new expiry.
func (s *Store) ExtendSubscription(ctx context.Context, userID string, days int) (time.Time, error) {
	var newEnds time.Time
	err := s.pool.QueryRow(ctx,
		`UPDATE users
		 SET subscription_ends = GREATEST(subscription_ends, now()) + make_interval(days => $1),
		     reminded = FALSE
		 WHERE id = $2
		 RETURNING subscription_ends`,
		days, userID,
	).Scan(&newEnds)
	if errors.Is(err, pgx.ErrNoRows) {
		return time.Time{}, ErrNotFound
	}
	return newEnds, err
}

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
	// How much of the purchased balance this cycle has already eaten. Needed
	// to state the allowance as it was rather than as it is left: without it
	// the only total available is "free + what remains", which shrinks as
	// traffic is charged and freezes the figure derived from it.
	LTECycleSpentBytes int64
	LTEFreeGBOverride  *int
	SquadTier          string

	// The two halves of the free period, each granted at most once. See
	// migration 0009: one bit could not describe two grants, and the second one
	// has to be collectable after the first has already moved the expiry date.
	TrialSignupGranted  bool
	TrialLinkGranted    bool
	BonusOfferDismissed bool

	// Which panel account is this user's. Recorded so the panel is addressed
	// by a stable UUID rather than by a name derived from a Telegram ID --
	// which a website-only account does not have.
	RemnawaveUUID     *string
	RemnawaveUsername string
}

// SubscriptionActive reports whether the paid period is still running.
func (u *User) SubscriptionActive() bool { return u.SubscriptionEnds.After(time.Now()) }

const userColumns = `
	id, telegram_id, telegram_tag, COALESCE(email, ''), subscription_ends,
	COALESCE(referrer_tag, ''), referred_people, gifted_subscriptions, created_at,
	lte_paid_balance_bytes, lte_cycle_start, lte_last_usage_bytes, lte_cycle_spent_bytes,
	lte_free_gb_override, squad_tier, remnawave_uuid, COALESCE(remnawave_username, ''),
	trial_signup_granted, trial_link_granted, bonus_offer_dismissed
`

func scanUser(row pgx.Row) (*User, error) {
	var u User
	err := row.Scan(
		&u.ID, &u.TelegramID, &u.TelegramTag, &u.Email, &u.SubscriptionEnds,
		&u.ReferrerTag, &u.ReferredPeople, &u.GiftedSubs, &u.CreatedAt,
		&u.LTEPaidBalanceBytes, &u.LTECycleStart, &u.LTELastUsageBytes, &u.LTECycleSpentBytes,
		&u.LTEFreeGBOverride, &u.SquadTier, &u.RemnawaveUUID, &u.RemnawaveUsername,
		&u.TrialSignupGranted, &u.TrialLinkGranted, &u.BonusOfferDismissed,
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

// UserByEmail looks a user up case-insensitively, following a merge.
//
// Addresses are stored as the user typed them, but nobody expects
// Bob@example.com and bob@example.com to be different accounts -- and treating
// them as different would let one person hold two accounts on one mailbox.
//
// The merge walk matters because an address can outlive the row it was
// registered on. Someone who signed up by email and then linked their Telegram
// account has their website row folded into the Telegram one; the address
// stays where it was, and a sign-in with it has to land on the account that is
// actually live rather than on a row with no subscription and no panel profile.
func (s *Store) UserByEmail(ctx context.Context, email string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`WITH RECURSIVE chain AS (
			SELECT id, merged_into, 0 AS depth FROM users WHERE lower(email) = lower($1)
			UNION ALL
			SELECT u.id, u.merged_into, chain.depth + 1
			FROM users u JOIN chain ON u.id = chain.merged_into
			WHERE chain.depth < 8
		)
		SELECT `+userColumns+` FROM users
		WHERE id = (SELECT id FROM chain WHERE merged_into IS NULL LIMIT 1)`,
		strings.TrimSpace(email)))
}

func (s *Store) UserByTelegramID(ctx context.Context, telegramID int64) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE telegram_id = $1`, telegramID))
}

func (s *Store) UserByTag(ctx context.Context, tag string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE lower(telegram_tag) = lower($1)`, strings.TrimSpace(tag)))
}

// referrerMatches is how `users.referrer_tag` finds the person it names.
//
// It holds a Telegram tag for anyone who has one and an email address for
// anyone who does not: a referrer who signed up on the website has no tag to
// be named by, and before this they could be named and then never credited.
// The two cannot collide -- an address always has an `@` and a tag never does.
//
// Kept identical to `_REFERRER_MATCHES` in shared/tgvpn_shared/db/users.py.
// A payment made in the bot is credited by that one and a payment made here by
// this one; if they disagreed, whether a referrer got their bonus would depend
// on where their invitee happened to pay.
const referrerMatches = `
	$1 <> ''
	AND (lower(telegram_tag) = lower($1) OR lower(email) = lower($1))`

// UserByReferrerHandle finds whoever a customer named as their referrer,
// whether they typed a Telegram tag or an email address.
func (s *Store) UserByReferrerHandle(ctx context.Context, handle string) (*User, error) {
	return scanUser(s.pool.QueryRow(ctx,
		`SELECT `+userColumns+` FROM users WHERE `+referrerMatches, strings.TrimSpace(handle)))
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

// CreateTelegramUser registers someone arriving through the Telegram login
// widget who has never opened the bot.
//
// The counterpart to CreateEmailUser, and admitted on the same grounds: the
// widget payload is HMAC-signed with the bot's own token, so the identity is
// proven before this is reached. `email` stays NULL — they have not given one,
// and the schema has never required it.
//
// Upserted rather than inserted because two tabs finishing the widget at the
// same moment would otherwise race on `telegram_id`'s unique index, and the
// loser would see an error on a login that had in fact just succeeded. The tag
// is refreshed on the way through: it is what referrals are matched by, and a
// customer who renames themselves on Telegram should not stop being findable.
func (s *Store) CreateTelegramUser(ctx context.Context, telegramID int64, tag string) (*User, error) {
	var id string
	err := s.pool.QueryRow(ctx,
		`INSERT INTO users (telegram_id, telegram_tag, subscription_ends, created_at)
		 VALUES ($1, $2, to_timestamp(0), now())
		 ON CONFLICT (telegram_id) DO UPDATE SET telegram_tag = EXCLUDED.telegram_tag
		 RETURNING id`,
		telegramID, strings.TrimSpace(tag),
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
		 WHERE `+referrerMatches, strings.TrimSpace(referrerTag))
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
// GrantTrial gives a user their free days, once and only once.
//
// The "only once" is in the WHERE clause rather than in a check the caller
// makes first, because the cabinet fires several requests at the same moment
// and more than one of them resolves the panel profile. Two of those read
// `subscription_ends` as still-unset four milliseconds apart and both granted,
// so a thirty-day trial arrived as sixty. Postgres serialises the update on
// the row, so exactly one of them can match here.
//
// The bool reports whether this call was the one that granted.
func (s *Store) GrantTrial(ctx context.Context, userID string, days int) (time.Time, bool, error) {
	var ends time.Time
	err := s.pool.QueryRow(ctx,
		`UPDATE users
		 SET subscription_ends = now() + make_interval(days => $1),
		     trial_signup_granted = TRUE,
		     reminded = FALSE
		 WHERE id = $2
		   AND NOT trial_signup_granted
		   AND (subscription_ends IS NULL OR subscription_ends <= to_timestamp(0))
		   -- ...and this Telegram account has not already collected one on a
		   -- row it has since been detached from. The flag above is per row,
		   -- so unlinking and signing up again minted a fresh seven days, and
		   -- linking back merged them onto the pile: the free period was
		   -- limited only by how many times somebody cared to go round.
		   AND NOT EXISTS (
		       SELECT 1
		       FROM telegram_link_history history
		       JOIN users prior ON prior.id = history.user_id
		       WHERE history.telegram_id = users.telegram_id
		         AND prior.trial_signup_granted
		   )
		 RETURNING subscription_ends`,
		days, userID,
	).Scan(&ends)
	if errors.Is(err, pgx.ErrNoRows) {
		// Either somebody else granted it a moment ago, or this account has
		// had a subscription before. Both mean "not this call", not an error.
		return time.Time{}, false, nil
	}
	if err != nil {
		return time.Time{}, false, err
	}
	return ends, true, nil
}

// GrantLinkBonus pays the second half of the free period: the days earned by
// connecting a second identity to an account that had one.
//
// Deliberately not conditional on the subscription being empty -- that is the
// difference from GrantTrial. This lands *on top* of the signup trial, which
// is the whole point, so `GREATEST(subscription_ends, now())` is what stops it
// being back-dated into a period a lapsed account never had.
//
// Kept identical to UserRepository.grant_link_bonus on the Python side, which
// pays the same bonus for the mirror-image case (Telegram attached to a
// website account). Both are guarded by the same flag, so whichever fires
// first is the only one that pays.
func (s *Store) GrantLinkBonus(ctx context.Context, userID string, days int) (time.Time, bool, error) {
	var ends time.Time
	err := s.pool.QueryRow(ctx,
		`UPDATE users
		 SET subscription_ends = GREATEST(subscription_ends, now()) + make_interval(days => $1),
		     trial_link_granted = TRUE,
		     reminded = FALSE
		 WHERE id = $2 AND NOT trial_link_granted
		 RETURNING subscription_ends`,
		days, userID,
	).Scan(&ends)
	if errors.Is(err, pgx.ErrNoRows) {
		return time.Time{}, false, nil
	}
	if err != nil {
		return time.Time{}, false, err
	}
	return ends, true, nil
}

// DismissBonusOffer records that the customer asked not to be shown the offer
// again. Stored on the account rather than in the browser, so the answer holds
// in the bot too -- it is one offer about one account.
func (s *Store) DismissBonusOffer(ctx context.Context, userID string) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE users SET bonus_offer_dismissed = TRUE WHERE id = $1`, userID)
	return err
}

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

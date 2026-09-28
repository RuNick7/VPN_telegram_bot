-- The trial becomes two halves: 7 days for signing up, 7 more for connecting
-- the second identity.
--
-- Until now "has this person had their free period?" was answered by
-- `subscription_ends > epoch 0`, which is a single bit and cannot describe two
-- grants. It also cannot survive the thing this feature is built on: an
-- account that signed up on the website and then attaches Telegram must be
-- able to collect a second grant *after* the first has already moved the date.
--
-- Two flags, therefore, each recording one grant that can happen at most once
-- per surviving account. Their sum is the cap: nobody can hold more than
-- 7 + 7 free days no matter which order they arrive in, and a merge folds the
-- flags together with the days, so joining two accounts that each collected a
-- signup grant does not also earn the link bonus.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS trial_signup_granted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS trial_link_granted   BOOLEAN NOT NULL DEFAULT FALSE,
    -- The customer pressed "больше не показывать" on the offer.
    ADD COLUMN IF NOT EXISTS bonus_offer_dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    -- The bot has made its one offer. Separate from the dismissal above
    -- because they answer different questions: one is "they said stop", the
    -- other is "we have already asked in this channel".
    ADD COLUMN IF NOT EXISTS bonus_offer_shown_in_bot BOOLEAN NOT NULL DEFAULT FALSE;

-- Everyone who already has a subscription has had their signup grant, whether
-- it came from the bot or the site. Without this they would each be handed a
-- fresh 7 days the next time their row was read.
UPDATE users SET trial_signup_granted = TRUE
WHERE subscription_ends > to_timestamp(0);

-- Binding an address to an account that already exists.
--
-- Not the same thing as `magic_link_tokens`, which are keyed by *email* and
-- sign somebody in -- deliberately, so that endpoint cannot be used to ask
-- whether an address has an account. These are keyed by user: the account is
-- already known and what is being proved is that the person driving it also
-- controls the mailbox.
--
-- Hashed like every other token here, so a database dump yields nothing that
-- can be redeemed.
CREATE TABLE IF NOT EXISTS email_verifications (
    token_hash  BYTEA PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_email_verifications_user
    ON email_verifications (user_id) WHERE consumed_at IS NULL;

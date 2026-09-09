-- Identity rework: our own IDs become the primary handle for a person.
--
-- Until now `telegram_id` was the identity. Everything keyed off it: the panel
-- username was literally str(telegram_id), payments credited by it, promo
-- usage referenced it. That made Telegram a hard dependency for existing at
-- all -- someone who signed up on the website could be charged but never
-- credited, because the webhook had no way to name them.
--
-- `users.id` has existed since 0001 for exactly this. What changes now is that
-- application code starts using it.
--
-- Nothing is renamed in Remnawave. Accounts already named str(telegram_id)
-- keep that name; `remnawave_uuid` records the panel's own UUID so we address
-- them by something stable instead, and new accounts get a name derived from
-- our UUID. The backfill is lazy -- the first lookup of a legacy user stores
-- their UUID -- because a bulk rename against a live panel is exactly the kind
-- of operation that is not worth the risk.

-- Following a merge chain, and finding orphaned rows during cleanup.
CREATE INDEX IF NOT EXISTS idx_users_merged_into ON users (merged_into)
    WHERE merged_into IS NOT NULL;

-- Looking a user up by their panel account, which is what the reconciliation
-- jobs iterate over.
CREATE INDEX IF NOT EXISTS idx_users_remnawave_uuid ON users (remnawave_uuid)
    WHERE remnawave_uuid IS NOT NULL;

-- The panel username we actually created for this user.
--
-- Distinct from remnawave_uuid because the two answer different questions:
-- the UUID is how we address the account, the username is what an operator
-- sees in the panel and what legacy lookups match on. Recording it means a
-- support question ("which panel row is this person?") does not require a
-- lookup that might fail.
ALTER TABLE users ADD COLUMN IF NOT EXISTS remnawave_username TEXT;

-- One-time tokens for attaching a Telegram account to a website account.
--
-- The website mints one, the user opens t.me/<bot>?start=link_<token>, and the
-- bot redeems it. That is the whole handshake: the token proves the person
-- driving the browser session and the person in the Telegram chat are the
-- same, without either side having to type an ID at the other.
CREATE TABLE account_link_tokens (
    -- Hashed, like every other credential here: the plaintext exists only in
    -- the link the user was handed.
    token_hash  BYTEA PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    -- Kept rather than deleted on redemption so a replayed link is
    -- distinguishable from one that never existed.
    consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_account_link_tokens_user ON account_link_tokens (user_id);
CREATE INDEX idx_account_link_tokens_expiry ON account_link_tokens (expires_at);

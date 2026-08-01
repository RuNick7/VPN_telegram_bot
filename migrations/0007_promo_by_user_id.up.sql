-- Promo codes redeemable by anyone, not only by Telegram accounts.
--
-- `promo_usage.telegram_id` was a NOT NULL foreign key into
-- `users(telegram_id)`, so a website account -- which has no Telegram ID at
-- all -- could not redeem a code even though it is a perfectly real customer.
-- Gifts were the sharpest edge of that: somebody buys a gift, hands the code
-- to a friend, and the friend cannot use it unless they happen to be a
-- Telegram user.
--
-- Usage is now recorded against `users.id`, which every account has. The
-- Telegram ID stays as a column because it is what an operator recognises in
-- support, but nothing keys on it any more.

ALTER TABLE promo_usage ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users (id);

-- Backfill from the Telegram ID each existing row already carries.
UPDATE promo_usage pu
SET user_id = u.id
FROM users u
WHERE pu.user_id IS NULL AND u.telegram_id = pu.telegram_id;

-- Any row we could not match has no owner we can name; deleting it would
-- silently free a one-time code for re-use, so it stays and simply never
-- matches a claim.

-- The foreign key is what made a Telegram ID mandatory. Dropping it lets a
-- website account own a usage row; the column keeps its value for history.
ALTER TABLE promo_usage DROP CONSTRAINT IF EXISTS promo_usage_telegram_id_fkey;
ALTER TABLE promo_usage ALTER COLUMN telegram_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_promo_usage_user_id ON promo_usage (user_id);

-- One row per (code, user). This is what makes the claim safe under a race:
-- two people redeeming the same one-time code, or one person double-clicking,
-- collide on the index instead of both being credited.
CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_usage_code_user
    ON promo_usage (code, user_id) WHERE user_id IS NOT NULL;

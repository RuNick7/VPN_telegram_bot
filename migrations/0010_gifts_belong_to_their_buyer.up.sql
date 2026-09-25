-- A gift code has to be findable by whoever paid for it.
--
-- `creator_id` is a BIGINT holding a Telegram ID, so a gift bought on the
-- website recorded no creator at all. Two things followed from that, and both
-- are real money:
--
--   * The code was delivered only as a Telegram message. A buyer with no
--     Telegram account got nothing -- the code existed, was paid for, and
--     there was no way to reach it from anywhere.
--   * The "you cannot redeem your own gift" check compares Telegram IDs, so a
--     website buyer could simply activate the gift they had just bought.
--
-- `creator_user_id` is the internal id every account has, including one that
-- has never touched Telegram. `creator_id` stays: it is what an operator
-- recognises in support, and nothing is gained by rewriting history.

ALTER TABLE promo_codes
    ADD COLUMN IF NOT EXISTS creator_user_id UUID REFERENCES users (id),
    -- Ordering. Without it the site can only show a customer their gifts in
    -- whatever order the table happens to return them.
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Backfill from the Telegram ID each existing gift already carries. Codes
-- created by an operator have no creator of either kind and stay that way.
UPDATE promo_codes p
SET creator_user_id = u.id
FROM users u
WHERE p.creator_user_id IS NULL
  AND p.creator_id IS NOT NULL
  AND u.telegram_id = p.creator_id;

CREATE INDEX IF NOT EXISTS idx_promo_codes_creator_user
    ON promo_codes (creator_user_id) WHERE creator_user_id IS NOT NULL;

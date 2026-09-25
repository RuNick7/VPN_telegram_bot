-- Deleting a user must not require erasing what they redeemed.
--
-- `promo_usage.user_id` referenced `users(id)` with the implicit default
-- action, RESTRICT, so the admin bot's "delete user" button failed outright
-- for anyone who had ever redeemed a code -- 82 real accounts on this
-- deployment alone, not an edge case. The operator saw a raw Postgres
-- constraint error and nothing else.
--
-- SET NULL is safe on both claim shapes in `try_claim_promo_usage_by_user_id`.
-- A one-time code's claim is guarded by the *existence* of any row for that
-- code, `user_id` and all -- nulling it out does not reopen the code. A
-- reusable code's claim is guarded by (code, user_id): the deleted user
-- cannot re-claim it because they no longer exist to try, and nobody else's
-- claim was ever keyed to their id. The row survives with its `code` and
-- `telegram_id` intact, which is what a "was this code used" check and a
-- support lookup by Telegram ID both still need.

ALTER TABLE promo_usage DROP CONSTRAINT IF EXISTS promo_usage_user_id_fkey;
ALTER TABLE promo_usage
    ADD CONSTRAINT promo_usage_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL;

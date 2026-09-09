-- A Telegram account can be detached from one account and attached to another.
--
-- Detaching frees the Telegram ID, and the bot creates a fresh row the next
-- time that person opens it. That row would come with a fresh signup trial,
-- which turns the free period into something renewable: unlink, /start, link
-- back, and the merge adds the new row's days to the old account. Seven days
-- per round trip, repeatable, a few clicks each.
--
-- So an unlink is remembered. The bot asks this table before granting, and a
-- Telegram account that has already had its trial through some account does
-- not get another. Nothing else is gated on it: the person still gets an
-- account, a panel profile and a working link -- just not a second free week.
--
-- It doubles as the answer to "which account was this Telegram attached to
-- before?", which support cannot otherwise reconstruct once the column is
-- cleared.

CREATE TABLE IF NOT EXISTS telegram_link_history (
    telegram_id BIGINT PRIMARY KEY,
    -- No foreign key on purpose: this outlives the account it points at, and
    -- an account being deleted must not quietly restore the trial.
    user_id     UUID,
    unlinked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A payment row is a payment id and a status, and nothing else.
--
-- That is enough to answer "did this go through?" from the browser, which is
-- all it was ever asked. It is not enough for the other question, the one that
-- costs money: a payment stuck in `processing_error` means somebody paid and
-- was not credited, and finding out *who* meant reading the YooKassa dashboard
-- and matching timestamps by hand. One such payment sat unnoticed for a day
-- because nothing in the admin bot could show it.
--
-- Three columns, all written at creation time by whichever side created it.
-- Status stays exactly as it was -- owned by the Python webhook, and only it,
-- because only it re-fetches the payment from YooKassa before believing it.

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users (id),
    -- "subscription" | "gift" | "traffic". What the money was for, so a stuck
    -- payment can be described rather than only listed.
    ADD COLUMN IF NOT EXISTS purpose TEXT NOT NULL DEFAULT '',
    -- What crediting it would have granted, so an operator fixing one by hand
    -- does not have to work it back out from the amount.
    ADD COLUMN IF NOT EXISTS days INTEGER NOT NULL DEFAULT 0;

-- The attention list reads exactly this: everything that is not settled.
-- Partial, because succeeded rows are almost all of them and are never in it.
CREATE INDEX IF NOT EXISTS idx_payments_unsettled
    ON payments (updated_at DESC) WHERE status <> 'succeeded';

DROP INDEX IF EXISTS idx_payments_unsettled;

ALTER TABLE payments
    DROP COLUMN IF EXISTS user_id,
    DROP COLUMN IF EXISTS purpose,
    DROP COLUMN IF EXISTS days;

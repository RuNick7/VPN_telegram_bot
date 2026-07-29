DROP TABLE IF EXISTS job_runs;

DROP INDEX IF EXISTS idx_users_lte_cycle_start;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_squad_tier_check;

ALTER TABLE users
    DROP COLUMN IF EXISTS lte_paid_balance_bytes,
    DROP COLUMN IF EXISTS lte_cycle_start,
    DROP COLUMN IF EXISTS lte_cycle_spent_bytes,
    DROP COLUMN IF EXISTS lte_blocked,
    DROP COLUMN IF EXISTS lte_last_usage_bytes,
    DROP COLUMN IF EXISTS squad_tier;

-- Phase 3: FREE-tier demotion and LTE traffic quotas.
--
-- Two things are being recorded here:
--
-- 1. Per-user LTE state. LTE is a metered squad: every user gets a free
--    allowance per cycle and can buy more on top. Kept as columns on `users`
--    rather than a side table because it is strictly one row per user and
--    every read of it already has the user row in hand.
--
-- 2. Scheduler job outcomes. The FREE tier works by keeping the panel account
--    alive forever and letting a background job move users between squads, so
--    that job is the only thing standing between an expired subscription and
--    continued paid access. `job_runs` is what makes its silence detectable:
--    the health monitor alerts when a job has not *succeeded* recently, which
--    a crashed or never-scheduled job cannot fake.

ALTER TABLE users
    -- Purchased LTE traffic still available, across cycles.
    ADD COLUMN lte_paid_balance_bytes BIGINT NOT NULL DEFAULT 0,
    -- Start of the user's current quota window. NULL until their first run.
    ADD COLUMN lte_cycle_start TIMESTAMPTZ,
    -- Purchased bytes already consumed within the current window. Reset on
    -- rollover; the balance itself carries over.
    ADD COLUMN lte_cycle_spent_bytes BIGINT NOT NULL DEFAULT 0,
    -- Whether LTE access is currently withheld (quota exhausted, or the
    -- subscription lapsed).
    ADD COLUMN lte_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    -- Last observed usage in the current window, for reporting.
    ADD COLUMN lte_last_usage_bytes BIGINT NOT NULL DEFAULT 0,
    -- Last tier the demotion job put this user in: 'paid', 'free', or
    -- 'unknown' before the job has ever seen them. Purely observational --
    -- the panel is authoritative -- but it makes "who did we just demote"
    -- answerable without re-reading every user from the panel.
    ADD COLUMN squad_tier TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE users
    ADD CONSTRAINT users_squad_tier_check CHECK (squad_tier IN ('unknown', 'paid', 'free'));

-- Finding everyone whose quota window has rolled over, without a full scan.
CREATE INDEX idx_users_lte_cycle_start ON users (lte_cycle_start)
    WHERE lte_cycle_start IS NOT NULL;

CREATE TABLE job_runs (
    job_name             TEXT PRIMARY KEY,
    last_attempt_at      TIMESTAMPTZ,
    -- Deliberately separate from last_attempt_at: a job that runs every 5
    -- minutes and fails every time still has a fresh attempt, and staleness
    -- has to be judged on success alone.
    last_success_at      TIMESTAMPTZ,
    last_error           TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_duration_ms     INTEGER
);

-- What the monitors did, so the admin chat does not have to be the record.
--
-- Both squad monitors ran every few minutes and messaged the admins on any
-- pass that changed anything. In practice that is a message every few minutes
-- all day, each one reporting a single routine demotion -- and a channel that
-- noisy is one nobody reads, which is exactly where a real alert goes to die.
--
-- The counts belong in the daily report instead. They cannot be counters in
-- memory: admin_bot restarts on every deploy, and a report that silently
-- forgets half a day is worse than the noise it replaced. So each action
-- lands here and the report reads a day's worth back.
--
-- Append-only and deliberately small. Not an audit log of the panel -- the
-- panel has its own -- just enough to answer "what did the enforcement do
-- yesterday, and to whom".

CREATE TABLE IF NOT EXISTS enforcement_events (
    id        BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Which monitor acted, by its JOB_NAME, so a surprising number can be
    -- traced back to the job that produced it.
    job       TEXT NOT NULL,
    -- 'blocked' | 'unblocked' | 'recut' | 'demoted' | 'promoted'. Left as free
    -- text rather than an enum: adding an outcome should be a code change, not
    -- a migration on a table nothing joins against.
    action    TEXT NOT NULL,
    -- Telegram ID, our UUID, or the panel's ref -- whichever the monitor had.
    -- Only ever read by a human, so it is not keyed to anything.
    subject   TEXT NOT NULL DEFAULT ''
);

-- Every read is "the last N hours", and the prune is "older than N days".
CREATE INDEX IF NOT EXISTS idx_enforcement_events_ts ON enforcement_events (ts DESC);

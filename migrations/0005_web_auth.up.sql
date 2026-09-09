-- Website authentication state: sessions, magic-link tokens, rate limiting.
--
-- All three lived in module-level dicts in the FastAPI backend this replaces.
-- That meant every restart logged everybody out, and a second instance could
-- never be run because neither would see the other's sessions or rate-limit
-- counters. Putting them in Postgres fixes both at once and is the reason the
-- Go rewrite can be deployed more than once.
--
-- No password column anywhere, by design: the site authenticates by emailed
-- magic link or by Telegram login widget, so there is no password hash to
-- leak.

CREATE TABLE web_sessions (
    -- SHA-256 of the token handed to the browser, never the token itself: a
    -- database leak must not yield working sessions.
    token_hash   BYTEA PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent   TEXT NOT NULL DEFAULT '',
    ip           TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_web_sessions_user ON web_sessions (user_id);
CREATE INDEX idx_web_sessions_expiry ON web_sessions (expires_at);

CREATE TABLE magic_link_tokens (
    -- Hashed for the same reason as sessions. The plaintext exists only in
    -- the email that was sent.
    token_hash BYTEA PRIMARY KEY,
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    -- Set when redeemed. A row is kept rather than deleted so a replayed link
    -- can be told apart from one that never existed.
    consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_magic_link_email ON magic_link_tokens (email);
CREATE INDEX idx_magic_link_expiry ON magic_link_tokens (expires_at);

CREATE TABLE auth_rate_limits (
    -- Whatever is being limited: "magic:<email>", "ip:<addr>".
    bucket        TEXT PRIMARY KEY,
    attempts      INTEGER NOT NULL DEFAULT 0,
    window_starts TIMESTAMPTZ NOT NULL DEFAULT now()
);

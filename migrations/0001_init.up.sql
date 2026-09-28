-- Identity-ready core schema, replacing user_bot/data/subscription.db (SQLite).
--
-- `users` unifies the old `subscription` table (keyed by telegram_id) with a
-- new internal `id` identity, so a person can exist without a telegram_id at
-- all (website-first signup, Phase 4). Application code in Phase 1/2/3 keeps
-- addressing users by telegram_id; `id`/`remnawave_uuid`/`merged_into` are
-- schema-ready placeholders Phase 4 will actually populate and use.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id           BIGINT UNIQUE,
    telegram_tag          TEXT NOT NULL DEFAULT '',
    email                 TEXT UNIQUE,
    remnawave_uuid        UUID,
    merged_into           UUID REFERENCES users (id),
    subscription_ends     TIMESTAMPTZ NOT NULL DEFAULT to_timestamp(0),
    referrer_tag          TEXT,
    is_referred           BOOLEAN NOT NULL DEFAULT FALSE,
    referred_people       INTEGER NOT NULL DEFAULT 0,
    gifted_subscriptions  INTEGER NOT NULL DEFAULT 0,
    reminded              BOOLEAN NOT NULL DEFAULT FALSE,
    nurture_stage         INTEGER NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE promo_codes (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    type        TEXT NOT NULL,
    value       INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    one_time    BOOLEAN NOT NULL DEFAULT FALSE,
    creator_id  BIGINT
);

CREATE TABLE promo_usage (
    id           BIGSERIAL PRIMARY KEY,
    code         TEXT NOT NULL,
    telegram_id  BIGINT NOT NULL REFERENCES users (telegram_id),
    used_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_promo_usage_code ON promo_usage (code);
CREATE INDEX idx_promo_usage_telegram_id ON promo_usage (telegram_id);

CREATE TABLE payments (
    id          BIGSERIAL PRIMARY KEY,
    payment_id  TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bot_events (
    id             BIGSERIAL PRIMARY KEY,
    telegram_id    BIGINT NOT NULL DEFAULT 0,
    callback_data  TEXT NOT NULL DEFAULT '',
    step           TEXT NOT NULL DEFAULT '',
    ts             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bot_events_telegram_id ON bot_events (telegram_id);

-- admin_bot's own operator-role table. Renamed from the old `users` (SQLite,
-- admin_bot/app/db/sqlite.py) to avoid colliding with the new customer
-- identity `users` table above -- different concept, same old name.
CREATE TABLE admin_operators (
    tg_id            BIGINT PRIMARY KEY,
    role             TEXT NOT NULL DEFAULT 'user',
    selected_server  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

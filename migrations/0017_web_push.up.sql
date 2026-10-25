-- Web Push: notifications from the site to the browsers a customer allowed.
--
-- Only the website reads and writes these. The bots tell Telegram users the
-- same things in Telegram; push exists for the people the bot cannot reach
-- and for those who would rather hear it from the installed app.

-- One row per browser. The endpoint is the push service's URL for that browser
-- and identifies it globally, so a browser that signs into another account
-- moves its row there rather than notifying both.
CREATE TABLE push_subscriptions (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL UNIQUE,
    -- The browser's keys (RFC 8291), base64url. Payloads are encrypted to
    -- them, so the push service relays text it cannot read.
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Refreshed every time the page re-registers the browser. Only for
    -- support to tell a live device from a forgotten one.
    seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_push_subscriptions_user ON push_subscriptions (user_id);

-- What a customer wants to hear about. No row means the defaults, which are
-- the important things only: the subscription running out, and support
-- answering. A payment going through is off by default -- the customer is
-- usually looking at the page that says so.
CREATE TABLE push_preferences (
    user_id     UUID PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    expiry      BOOLEAN NOT NULL DEFAULT TRUE,
    support     BOOLEAN NOT NULL DEFAULT TRUE,
    payment     BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- What has been sent, so a restart or a second pass never sends it again. The
-- key names the event: 'expiry:<ends>:3', 'support:<message id>',
-- 'payment:<payment id>'. A row is written before sending -- the claim -- and
-- removed again if no browser took it, so a failure is retried.
CREATE TABLE push_sent (
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    event_key   TEXT NOT NULL,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_key)
);
CREATE INDEX idx_push_sent_at ON push_sent (sent_at);

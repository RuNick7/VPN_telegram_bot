-- Support tickets: a customer writes on the website, an operator answers in
-- Telegram.
--
-- The two ends never talk to each other directly. The website holds no admin
-- bot token -- it is the most exposed process in the deployment and has no
-- business carrying one -- so it only ever writes here, and admin_bot carries
-- what it finds to the operators' chats. That makes these tables an outbox as
-- much as a record: a message written while Telegram or the bot is down is
-- delivered late, never lost.
--
-- Who may write what is split the way payments are. The website creates
-- tickets, adds the customer's messages and lets them close their own; only
-- admin_bot records an operator's answer. `web/internal/store` has no function
-- that could do the latter, so the rule holds by absence rather than by
-- discipline.

CREATE TABLE support_tickets (
    -- Doubles as the number both sides quote at each other: "#123".
    id          BIGSERIAL PRIMARY KEY,
    -- Deleting a person takes their tickets with them. Nothing else points at
    -- a ticket, and a conversation whose author no longer exists is not
    -- something anybody goes back to read.
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subject     TEXT NOT NULL,
    -- 'open': waiting on us. 'answered': waiting on the customer.
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'answered', 'closed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Last time anybody wrote, or the status changed. Orders both lists, and
    -- decides when a ticket's files have been idle long enough to purge.
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at   TIMESTAMPTZ,
    closed_by   TEXT CHECK (closed_by IN ('user', 'admin')),
    -- When the operators were told the customer closed it. Only that kind of
    -- close needs announcing -- an operator who closed one already knows --
    -- and it is its own small outbox because the website cannot send it.
    close_announced_at TIMESTAMPTZ,
    -- When the customer last opened the thread. An operator's message newer
    -- than this is unread.
    user_read_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_support_tickets_user ON support_tickets (user_id, updated_at DESC);
-- The operators' queue: what is waiting on us, oldest first.
CREATE INDEX idx_support_tickets_status ON support_tickets (status, updated_at);

CREATE TABLE support_messages (
    id          BIGSERIAL PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    author      TEXT NOT NULL CHECK (author IN ('user', 'admin')),
    -- Which operator answered. NULL on the customer's own messages. Kept for
    -- the operators; the customer is shown "Поддержка", not a person.
    admin_telegram_id BIGINT,
    body        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The outbox. On a customer's message: when it reached the operators'
    -- chats. On an operator's: when the customer was told in Telegram -- or
    -- turned out to have no Telegram to be told in, which settles it the same.
    delivered_at        TIMESTAMPTZ,
    delivery_attempts   INTEGER NOT NULL DEFAULT 0,
    last_delivery_error TEXT
);
CREATE INDEX idx_support_messages_ticket ON support_messages (ticket_id, id);
-- What admin_bot polls every few seconds. Partial, so it stays the size of the
-- backlog -- normally nothing -- however long the history grows.
CREATE INDEX idx_support_messages_undelivered ON support_messages (id)
    WHERE delivered_at IS NULL;

CREATE TABLE support_attachments (
    -- Random rather than sequential: it goes into a URL, and although every
    -- read checks ownership anyway, there is no reason to publish a counter.
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id   BIGINT NOT NULL REFERENCES support_messages (id) ON DELETE CASCADE,
    file_name    TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   BIGINT NOT NULL CHECK (size_bytes >= 0),
    -- clock_timestamp(), not now(): a message's files are inserted in one
    -- transaction, now() would give them all the same instant, and the order
    -- the customer attached them in would be left to a random UUID.
    created_at   TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX idx_support_attachments_message ON support_attachments (message_id);

-- The bytes, kept apart from the row that describes them.
--
-- Apart so the daily dump admin_bot sends over Telegram can leave them out:
-- Telegram refuses a document above 50 MB, and a few screen recordings would
-- push every dump past that for good. Excluding only this table keeps the
-- restore consistent -- every attachment row comes back, and one without its
-- bytes is exactly what a file purged for age already looks like. A missing
-- row here is the one definition of "gone", whichever way it went.
CREATE TABLE support_attachment_data (
    attachment_id UUID PRIMARY KEY REFERENCES support_attachments (id) ON DELETE CASCADE,
    data          BYTEA NOT NULL
);
-- Stored as is, uncompressed and out of line. Photos and videos are compressed
-- already, so Postgres' own pass would spend CPU for nothing; and an
-- uncompressed out-of-line value can be read a slice at a time, which is what
-- lets a video be served by byte range without loading all of it per request.
ALTER TABLE support_attachment_data ALTER COLUMN data SET STORAGE EXTERNAL;

-- Which Telegram message carries which ticket, per operator chat.
--
-- The whole reply mechanism rests on this: an operator answers by replying to
-- a message, and this is how the bot knows which ticket that message belongs
-- to. It is also what makes delivery resumable -- a pass interrupted halfway
-- through a message's files resends only the ones that are not here yet.
CREATE TABLE support_telegram_messages (
    chat_id             BIGINT NOT NULL,
    telegram_message_id BIGINT NOT NULL,
    ticket_id           BIGINT NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    -- 'card': a ticket's header, which later messages reply to. 'text' and
    -- 'attachment': a customer message, or one of its files. 'notice':
    -- anything else said about the ticket.
    kind                TEXT NOT NULL,
    support_message_id  BIGINT REFERENCES support_messages (id) ON DELETE CASCADE,
    attachment_id       UUID REFERENCES support_attachments (id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, telegram_message_id)
);
CREATE INDEX idx_support_tg_ticket ON support_telegram_messages (ticket_id, chat_id);
CREATE INDEX idx_support_tg_message ON support_telegram_messages (support_message_id)
    WHERE support_message_id IS NOT NULL;

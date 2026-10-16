-- Server-check reports in support tickets, only with the customer's consent.
--
-- An operator asks from a ticket card in Telegram; the customer is asked in
-- user_bot what would be collected and answers yes or no. A yes yields a
-- one-time code the vpncheck program takes: it runs the check on the
-- customer's computer and attaches the report to this ticket -- after the
-- customer has seen the file and agreed once more.
--
-- The code is the report's only authorisation. It is stored as a hash, names
-- one ticket, expires, and stops working once a report is in. The website
-- never learns more from it than which ticket to write to, and writes there
-- as the customer, the way the customer's own messages are written.
CREATE TABLE support_diagnostics (
    id           BIGSERIAL PRIMARY KEY,
    ticket_id    BIGINT NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    -- The operator who asked, by Telegram id.
    requested_by BIGINT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The question in the customer's chat with user_bot, so the answer can
    -- replace its buttons.
    asked_chat_id    BIGINT,
    asked_message_id BIGINT,
    -- NULL until the customer answers. Nothing is collected before 'granted'.
    decision     TEXT CHECK (decision IN ('granted', 'declined')),
    decided_at   TIMESTAMPTZ,
    -- When the operators were told the answer. Its own small outbox, as the
    -- customer answers in user_bot and only admin_bot speaks to operators.
    decision_announced_at TIMESTAMPTZ,
    -- sha256 of the code, normalised (upper case, no separators). The code
    -- itself is shown to the customer once and kept nowhere.
    code_hash       BYTEA UNIQUE,
    code_expires_at TIMESTAMPTZ,
    -- The customer message the report arrived in.
    report_message_id BIGINT REFERENCES support_messages (id) ON DELETE SET NULL,
    reported_at  TIMESTAMPTZ,
    CHECK ((decision IS NULL) = (decided_at IS NULL)),
    CHECK ((decision = 'granted') = (code_hash IS NOT NULL AND code_expires_at IS NOT NULL))
);
CREATE INDEX idx_support_diagnostics_ticket ON support_diagnostics (ticket_id, created_at DESC);
-- What admin_bot polls with the rest of the support outbox.
CREATE INDEX idx_support_diagnostics_unannounced ON support_diagnostics (id)
    WHERE decided_at IS NOT NULL AND decision_announced_at IS NULL;

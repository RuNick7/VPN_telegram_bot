-- Server-check reports the vpncheck program sends into support tickets.
--
-- The customer presses «Отправить в поддержку» in the program; it sends the
-- report with their subscription link, and the site finds whose link it is
-- through the panel. The report lands as the customer's message in their
-- latest open ticket, or opens one, and reaches the operators through the
-- support outbox like any other message. Pressing the button is the consent:
-- nothing is sent before it, and the report has had keys, the link and the
-- customer's address cut out on their computer.
--
-- This table is what the site and admin_bot need on top of the message:
-- how many reports a customer sent today (the site allows a few), and which
-- reports admin_bot has asked the nodes' agents about.
CREATE TABLE vpncheck_reports (
    id           BIGSERIAL PRIMARY KEY,
    ticket_id    BIGINT NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    -- The customer message the report arrived in.
    message_id   BIGINT REFERENCES support_messages (id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- When admin_bot asked the nodes' agents for their side of the run and
    -- sent the operators what they found (or that there was nothing).
    node_logs_at TIMESTAMPTZ
);
-- The daily allowance counts through the ticket's owner, so a merge, which
-- moves tickets to the surviving account, carries the count with them.
CREATE INDEX idx_vpncheck_reports_ticket ON vpncheck_reports (ticket_id, created_at DESC);
-- Reports whose node logs are still to be fetched.
CREATE INDEX idx_vpncheck_reports_node_logs ON vpncheck_reports (id)
    WHERE node_logs_at IS NULL;

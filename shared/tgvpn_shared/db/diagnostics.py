"""
Requests for a server-check report in a support ticket.

admin_bot creates a request when an operator asks; user_bot records the
customer's answer, and with a yes the hash of the code they were given. The
report itself arrives through the website, which finds the request by that
hash -- see migrations/0016_support_diagnostics.up.sql for the whole flow.
"""

from __future__ import annotations

from ..support_diagnostics import REQUEST_TTL_SECONDS
from .pool import get_pool

_REQUEST = """
    SELECT
        d.id,
        d.ticket_id,
        d.requested_by,
        d.decision,
        d.asked_chat_id,
        d.asked_message_id,
        EXTRACT(EPOCH FROM d.created_at)::bigint AS created_at,
        EXTRACT(EPOCH FROM d.code_expires_at)::bigint AS code_expires_at,
        EXTRACT(EPOCH FROM d.reported_at)::bigint AS reported_at,
        d.created_at > now() - make_interval(secs => $2) AS fresh,
        t.subject,
        t.status,
        u.telegram_id
    FROM support_diagnostics d
    JOIN support_tickets t ON t.id = d.ticket_id
    JOIN users u ON u.id = t.user_id
"""


class SupportDiagnosticsRepository:
    async def create(self, ticket_id: int, requested_by: int) -> int | None:
        """
        A new request, or None when one is already waiting for the customer.

        The ticket row is locked for the check, so an operator pressing the
        button twice -- or two operators pressing it at once -- asks once.
        """
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                found = await connection.fetchval(
                    "SELECT id FROM support_tickets WHERE id = $1 FOR UPDATE", ticket_id
                )
                if found is None:
                    return None
                waiting = await connection.fetchval(
                    """
                    SELECT 1 FROM support_diagnostics
                    WHERE ticket_id = $1 AND decision IS NULL
                      AND created_at > now() - make_interval(secs => $2)
                    """,
                    ticket_id, REQUEST_TTL_SECONDS,
                )
                if waiting:
                    return None
                return int(await connection.fetchval(
                    """
                    INSERT INTO support_diagnostics (ticket_id, requested_by)
                    VALUES ($1, $2) RETURNING id
                    """,
                    ticket_id, requested_by,
                ))

    async def delete(self, request_id: int) -> None:
        """Forget a request whose question never reached the customer."""
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM support_diagnostics WHERE id = $1 AND decision IS NULL", request_id
        )

    async def record_question(self, request_id: int, chat_id: int, message_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE support_diagnostics SET asked_chat_id = $2, asked_message_id = $3
            WHERE id = $1
            """,
            request_id, chat_id, message_id,
        )

    async def get(self, request_id: int) -> dict | None:
        """A request with its ticket and the Telegram id of the ticket's owner."""
        pool = await get_pool()
        row = await pool.fetchrow(_REQUEST + " WHERE d.id = $1", request_id, REQUEST_TTL_SECONDS)
        return dict(row) if row else None

    async def grant(self, request_id: int, code_hash: bytes, ttl_seconds: int) -> int | None:
        """
        Record a yes and the code's hash. Returns when the code expires, or
        None if the request was answered already or has gone stale.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE support_diagnostics SET
                decision        = 'granted',
                decided_at      = now(),
                code_hash       = $2,
                code_expires_at = now() + make_interval(secs => $3)
            WHERE id = $1 AND decision IS NULL
              AND created_at > now() - make_interval(secs => $4)
            RETURNING EXTRACT(EPOCH FROM code_expires_at)::bigint
            """,
            request_id, code_hash, ttl_seconds, REQUEST_TTL_SECONDS,
        )

    async def decline(self, request_id: int) -> bool:
        """Record a no. False if the request was answered already or has gone stale."""
        pool = await get_pool()
        result = await pool.execute(
            """
            UPDATE support_diagnostics SET decision = 'declined', decided_at = now()
            WHERE id = $1 AND decision IS NULL
              AND created_at > now() - make_interval(secs => $2)
            """,
            request_id, REQUEST_TTL_SECONDS,
        )
        return result != "UPDATE 0"

    async def pending_announcements(self, limit: int = 20) -> list[dict]:
        """Answers the operators have not been told about, oldest first."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT d.id, d.ticket_id, d.decision, t.subject
            FROM support_diagnostics d
            JOIN support_tickets t ON t.id = d.ticket_id
            WHERE d.decided_at IS NOT NULL AND d.decision_announced_at IS NULL
            ORDER BY d.id
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def mark_announced(self, request_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE support_diagnostics SET decision_announced_at = now() WHERE id = $1",
            request_id,
        )

    async def pending_node_logs(self, limit: int = 5) -> list[dict]:
        """
        Reports whose node logs are still to be fetched, oldest first, with
        what the search needs: the report file, and the names the customer
        may have in the panel. Only once the report itself has reached the
        operators, so the logs arrive after it.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT d.id, d.ticket_id, t.subject,
                   (SELECT a.id::text FROM support_attachments a
                    WHERE a.message_id = m.id ORDER BY a.id LIMIT 1) AS attachment_id,
                   u.telegram_id, u.remnawave_username, u.remnawave_uuid::text AS remnawave_uuid
            FROM support_diagnostics d
            JOIN support_tickets t ON t.id = d.ticket_id
            JOIN users u ON u.id = t.user_id
            JOIN support_messages m ON m.id = d.report_message_id
            WHERE d.reported_at IS NOT NULL AND d.node_logs_at IS NULL
              AND m.delivered_at IS NOT NULL
            ORDER BY d.id
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def mark_node_logs(self, request_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE support_diagnostics SET node_logs_at = now() WHERE id = $1",
            request_id,
        )

"""
Server-check reports the vpncheck program sent into support tickets.

The website stores each report as the customer's message with the file
attached, plus a row here (migrations/0016_vpncheck_reports.up.sql). The
support outbox delivers the message like any other; admin_bot reads this
table only to ask the nodes' agents for their side of each run.
"""

from __future__ import annotations

from .pool import get_pool


class VpncheckReportRepository:
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
            SELECT r.id, r.ticket_id, t.subject,
                   (SELECT a.id::text FROM support_attachments a
                    WHERE a.message_id = m.id ORDER BY a.id LIMIT 1) AS attachment_id,
                   u.telegram_id, u.remnawave_username, u.remnawave_uuid::text AS remnawave_uuid
            FROM vpncheck_reports r
            JOIN support_tickets t ON t.id = r.ticket_id
            JOIN users u ON u.id = t.user_id
            JOIN support_messages m ON m.id = r.message_id
            WHERE r.node_logs_at IS NULL AND m.delivered_at IS NOT NULL
            ORDER BY r.id
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def mark_node_logs(self, report_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE vpncheck_reports SET node_logs_at = now() WHERE id = $1",
            report_id,
        )

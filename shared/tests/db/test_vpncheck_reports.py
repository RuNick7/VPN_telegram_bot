"""
Reports from the vpncheck program, as admin_bot reads them to ask the nodes.

The website writes them; what is pinned here is that admin_bot waits for the
report to reach the operators, finds what the node search needs, and asks
about each one once.
"""

import time

from tgvpn_shared.db import UserRepository, VpncheckReportRepository
from tgvpn_shared.db.pool import get_pool

reports = VpncheckReportRepository()
users = UserRepository()


async def _report(telegram_id: int = 555) -> tuple[int, int, str]:
    """A report as the website stores one: the customer's message, its file, and the row."""
    user_id = await users.insert_web_user(f"customer{telegram_id}@example.com", int(time.time()) + 86400)
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET telegram_id = $2, remnawave_username = 'u-abc' WHERE id = $1::uuid",
        user_id, telegram_id,
    )
    ticket_id = await pool.fetchval(
        "INSERT INTO support_tickets (user_id, subject) VALUES ($1::uuid, 'Проверка серверов') RETURNING id",
        user_id,
    )
    message_id = await pool.fetchval(
        "INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'user', 'отчёт') RETURNING id",
        ticket_id,
    )
    attachment_id = await pool.fetchval(
        """
        INSERT INTO support_attachments (message_id, file_name, content_type, size_bytes)
        VALUES ($1, 'vpncheck-report.txt', 'text/plain', 5) RETURNING id::text
        """,
        message_id,
    )
    report_id = await pool.fetchval(
        "INSERT INTO vpncheck_reports (ticket_id, message_id) VALUES ($1, $2) RETURNING id",
        ticket_id, message_id,
    )
    return int(report_id), int(message_id), attachment_id


async def test_node_logs_wait_for_the_report_to_reach_the_operators():
    report_id, message_id, attachment_id = await _report()
    assert await reports.pending_node_logs() == [], "not before the report itself is delivered"

    pool = await get_pool()
    await pool.execute("UPDATE support_messages SET delivered_at = now() WHERE id = $1", message_id)
    [pending] = await reports.pending_node_logs()
    assert pending["id"] == report_id and pending["attachment_id"] == attachment_id
    assert pending["subject"] == "Проверка серверов"
    assert (pending["telegram_id"], pending["remnawave_username"]) == (555, "u-abc")

    await reports.mark_node_logs(report_id)
    assert await reports.pending_node_logs() == []


async def test_reports_are_asked_about_oldest_first():
    first, first_message, _ = await _report(555)
    second, second_message, _ = await _report(556)
    pool = await get_pool()
    await pool.execute(
        "UPDATE support_messages SET delivered_at = now() WHERE id = ANY($1::bigint[])",
        [first_message, second_message],
    )
    assert [p["id"] for p in await reports.pending_node_logs()] == [first, second]
    assert [p["id"] for p in await reports.pending_node_logs(limit=1)] == [first]

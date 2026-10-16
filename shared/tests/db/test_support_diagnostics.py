"""
Requests for a server-check report: asked by admin_bot, answered in user_bot.

What matters is that one question is asked at a time, that it can be answered
once, that a stale one cannot be, and that the operators hear the answer.
"""

import time

from tgvpn_shared.db import SupportDiagnosticsRepository, UserRepository
from tgvpn_shared.db.pool import get_pool
from tgvpn_shared.support_diagnostics import CODE_TTL_SECONDS, REQUEST_TTL_SECONDS, hash_code

diagnostics = SupportDiagnosticsRepository()
users = UserRepository()
OPERATOR = 111


async def _ticket(telegram_id: int | None = 555) -> int:
    user_id = await users.insert_web_user(f"customer{telegram_id}@example.com", int(time.time()) + 86400)
    pool = await get_pool()
    if telegram_id:
        await pool.execute("UPDATE users SET telegram_id = $2 WHERE id = $1::uuid", user_id, telegram_id)
    return int(await pool.fetchval(
        "INSERT INTO support_tickets (user_id, subject) VALUES ($1::uuid, 'Не подключается') RETURNING id",
        user_id,
    ))


async def test_one_question_at_a_time_per_ticket():
    ticket_id = await _ticket()
    first = await diagnostics.create(ticket_id, OPERATOR)
    assert first is not None
    assert await diagnostics.create(ticket_id, OPERATOR) is None

    await diagnostics.decline(first)
    assert await diagnostics.create(ticket_id, OPERATOR) is not None


async def test_a_request_carries_its_ticket_and_who_may_answer():
    ticket_id = await _ticket(telegram_id=555)
    request_id = await diagnostics.create(ticket_id, OPERATOR)
    await diagnostics.record_question(request_id, 555, 42)

    request = await diagnostics.get(request_id)
    assert request["ticket_id"] == ticket_id
    assert request["telegram_id"] == 555
    assert request["subject"] == "Не подключается"
    assert request["decision"] is None and request["fresh"] is True
    assert (request["asked_chat_id"], request["asked_message_id"]) == (555, 42)


async def test_granting_stores_the_hash_and_expiry_once():
    request_id = await diagnostics.create(await _ticket(), OPERATOR)
    code_hash = hash_code("ABCD-EFGH-JKLM")

    expires_at = await diagnostics.grant(request_id, code_hash, CODE_TTL_SECONDS)
    assert abs(expires_at - (time.time() + CODE_TTL_SECONDS)) < 60
    # A second tap, or a no after the yes, changes nothing.
    assert await diagnostics.grant(request_id, hash_code("2345-6789-ZZZZ"), CODE_TTL_SECONDS) is None
    assert await diagnostics.decline(request_id) is False

    pool = await get_pool()
    stored = await pool.fetchval("SELECT code_hash FROM support_diagnostics WHERE id = $1", request_id)
    assert bytes(stored) == code_hash


async def test_a_stale_question_cannot_be_answered():
    request_id = await diagnostics.create(await _ticket(), OPERATOR)
    pool = await get_pool()
    await pool.execute(
        "UPDATE support_diagnostics SET created_at = now() - make_interval(secs => $2) WHERE id = $1",
        request_id, REQUEST_TTL_SECONDS + 60,
    )
    assert (await diagnostics.get(request_id))["fresh"] is False
    assert await diagnostics.grant(request_id, hash_code("ABCD-EFGH-JKLM"), CODE_TTL_SECONDS) is None
    assert await diagnostics.decline(request_id) is False


async def test_a_question_that_never_arrived_is_forgotten():
    ticket_id = await _ticket()
    request_id = await diagnostics.create(ticket_id, OPERATOR)
    await diagnostics.delete(request_id)
    assert await diagnostics.get(request_id) is None
    assert await diagnostics.create(ticket_id, OPERATOR) is not None


async def test_answers_wait_to_be_announced():
    granted = await diagnostics.create(await _ticket(), OPERATOR)
    declined = await diagnostics.create(await _ticket(telegram_id=556), OPERATOR)
    waiting = await diagnostics.create(await _ticket(telegram_id=557), OPERATOR)
    await diagnostics.grant(granted, hash_code("ABCD-EFGH-JKLM"), CODE_TTL_SECONDS)
    await diagnostics.decline(declined)

    pending = await diagnostics.pending_announcements()
    assert [(p["id"], p["decision"]) for p in pending] == [(granted, "granted"), (declined, "declined")]
    assert waiting not in [p["id"] for p in pending]

    await diagnostics.mark_announced(granted)
    assert [p["id"] for p in await diagnostics.pending_announcements()] == [declined]


async def test_node_logs_wait_for_the_report_to_reach_the_operators():
    ticket_id = await _ticket()
    request_id = await diagnostics.create(ticket_id, OPERATOR)
    await diagnostics.grant(request_id, hash_code("ABCD-EFGH-JKLM"), CODE_TTL_SECONDS)
    pool = await get_pool()
    await pool.execute("UPDATE users SET remnawave_username = 'u-abc' WHERE telegram_id = 555")
    # As the website stores a report: the customer's message, its file, and
    # the request pointing at it.
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
    await pool.execute(
        "UPDATE support_diagnostics SET reported_at = now(), report_message_id = $2 WHERE id = $1",
        request_id, message_id,
    )
    assert await diagnostics.pending_node_logs() == [], "not before the report itself is delivered"

    await pool.execute("UPDATE support_messages SET delivered_at = now() WHERE id = $1", message_id)
    [pending] = await diagnostics.pending_node_logs()
    assert pending["id"] == request_id and pending["attachment_id"] == attachment_id
    assert (pending["telegram_id"], pending["remnawave_username"]) == (555, "u-abc")

    await diagnostics.mark_node_logs(request_id)
    assert await diagnostics.pending_node_logs() == []

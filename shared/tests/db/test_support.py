"""
Support tickets, as admin_bot reads and writes them.

The website creates tickets; nothing on this side can. So the tickets here are
written with plain SQL in the shape the site writes them, and what is tested
is everything after that: the outbox that carries a customer's message to the
operators, the mapping that turns an operator's Telegram reply back into a
ticket, and the answer that comes back the other way.
"""

import time

import pytest

from tgvpn_shared.db import SupportRepository, UserRepository
from tgvpn_shared.db.pool import get_pool
from tgvpn_shared.identity import plan_merge

support = SupportRepository()
users = UserRepository()

ADMIN_CHAT = 111
OTHER_ADMIN_CHAT = 222


async def _customer(email: str = "customer@example.com") -> str:
    return await users.insert_web_user(email, int(time.time()) + 30 * 86400)


async def _ticket(user_id: str, subject: str = "Не подключается", body: str = "Помогите", files=()) -> tuple[int, int]:
    """Open a ticket the way the website does: ticket, first message, files."""
    pool = await get_pool()
    ticket_id = await pool.fetchval(
        "INSERT INTO support_tickets (user_id, subject) VALUES ($1::uuid, $2) RETURNING id",
        user_id, subject,
    )
    message_id = await _customer_message(ticket_id, body, files)
    return int(ticket_id), message_id


async def _customer_message(ticket_id: int, body: str, files=()) -> int:
    pool = await get_pool()
    message_id = await pool.fetchval(
        "INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'user', $2) RETURNING id",
        ticket_id, body,
    )
    for name, content_type, data in files:
        attachment_id = await pool.fetchval(
            """
            INSERT INTO support_attachments (message_id, file_name, content_type, size_bytes)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            message_id, name, content_type, len(data),
        )
        await pool.execute(
            "INSERT INTO support_attachment_data (attachment_id, data) VALUES ($1, $2)",
            attachment_id, data,
        )
    return int(message_id)


async def _close_as_customer(ticket_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE support_tickets
        SET status = 'closed', closed_at = now(), closed_by = 'user', updated_at = now()
        WHERE id = $1
        """,
        ticket_id,
    )


async def _status(ticket_id: int) -> str:
    pool = await get_pool()
    return await pool.fetchval("SELECT status FROM support_tickets WHERE id = $1", ticket_id)


# -- customer -> operators ----------------------------------------------------


async def test_a_new_ticket_is_waiting_to_be_delivered_with_everything_a_card_needs():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(
        user_id, files=[("screen.png", "image/png", b"\x89PNG....")]
    )

    [pending] = await support.pending_customer_messages()

    assert pending["id"] == message_id
    assert pending["ticket_id"] == ticket_id
    assert pending["opens_ticket"] is True
    assert pending["subject"] == "Не подключается"
    assert pending["email"] == "customer@example.com"
    assert pending["user_id"] == user_id
    assert isinstance(pending["subscription_ends"], int)
    [attachment] = pending["attachments"]
    assert attachment["file_name"] == "screen.png"
    assert attachment["size_bytes"] == 8
    # Metadata only: the bytes are fetched one file at a time, when sent.
    assert "data" not in attachment


async def test_a_follow_up_does_not_open_the_ticket_and_comes_after_it():
    user_id = await _customer()
    ticket_id, first = await _ticket(user_id)
    second = await _customer_message(ticket_id, "Ещё деталь")

    pending = await support.pending_customer_messages()

    assert [row["id"] for row in pending] == [first, second]
    assert [row["opens_ticket"] for row in pending] == [True, False]


async def test_a_delivered_message_leaves_the_outbox():
    user_id = await _customer()
    _, message_id = await _ticket(user_id)

    await support.mark_delivered(message_id)

    assert await support.pending_customer_messages() == []


async def test_failures_are_counted_and_keep_the_message_pending():
    user_id = await _customer()
    _, message_id = await _ticket(user_id)

    assert await support.record_delivery_failure(message_id, "timeout") == 1
    assert await support.record_delivery_failure(message_id, "timeout") == 2

    [pending] = await support.pending_customer_messages()
    assert pending["delivery_attempts"] == 2


async def test_an_operator_answer_is_not_mistaken_for_a_customer_message():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(user_id)
    await support.mark_delivered(message_id)

    await support.add_admin_reply(ticket_id, ADMIN_CHAT, "Ответ")

    assert await support.pending_customer_messages() == []


# -- which Telegram message is which ticket -------------------------------------


async def test_a_reply_to_any_part_of_a_delivered_message_finds_its_ticket():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(
        user_id, files=[("a.pdf", "application/pdf", b"%PDF-1.7")]
    )
    [pending] = await support.pending_customer_messages()
    attachment_id = pending["attachments"][0]["id"]

    await support.record_telegram_message(ADMIN_CHAT, 500, ticket_id, "card", support_message_id=message_id)
    await support.record_telegram_message(
        ADMIN_CHAT, 501, ticket_id, "attachment",
        support_message_id=message_id, attachment_id=attachment_id,
    )

    assert await support.ticket_for_telegram_message(ADMIN_CHAT, 500) == ticket_id
    assert await support.ticket_for_telegram_message(ADMIN_CHAT, 501) == ticket_id
    # The same message id in another chat is another message entirely.
    assert await support.ticket_for_telegram_message(OTHER_ADMIN_CHAT, 500) is None


async def test_delivered_parts_say_what_is_already_in_each_chat():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(
        user_id, files=[("a.pdf", "application/pdf", b"%PDF-1.7")]
    )
    [pending] = await support.pending_customer_messages()
    attachment_id = pending["attachments"][0]["id"]

    # A long text went out in two pieces; its files reply to the first.
    await support.record_telegram_message(ADMIN_CHAT, 700, ticket_id, "card", support_message_id=message_id)
    await support.record_telegram_message(ADMIN_CHAT, 701, ticket_id, "text", support_message_id=message_id)
    await support.record_telegram_message(
        ADMIN_CHAT, 702, ticket_id, "attachment",
        support_message_id=message_id, attachment_id=attachment_id,
    )

    parts = await support.delivered_parts(message_id)

    assert parts[(ADMIN_CHAT, None)] == 700
    assert parts[(ADMIN_CHAT, attachment_id)] == 702
    assert (OTHER_ADMIN_CHAT, None) not in parts


async def test_recording_the_same_telegram_message_twice_is_harmless():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(user_id)

    for _ in range(2):
        await support.record_telegram_message(ADMIN_CHAT, 800, ticket_id, "card", support_message_id=message_id)

    assert await support.ticket_for_telegram_message(ADMIN_CHAT, 800) == ticket_id


async def test_follow_ups_thread_onto_the_newest_card():
    user_id = await _customer()
    ticket_id, message_id = await _ticket(user_id)
    await support.record_telegram_message(ADMIN_CHAT, 10, ticket_id, "card", support_message_id=message_id)
    await support.record_telegram_message(ADMIN_CHAT, 90, ticket_id, "card")

    assert await support.card_for(ticket_id, ADMIN_CHAT) == 90
    assert await support.card_for(ticket_id, OTHER_ADMIN_CHAT) is None


# -- the operators' answer ------------------------------------------------------


async def test_an_answer_marks_the_ticket_answered_and_waits_to_be_announced():
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id)

    reply_id = await support.add_admin_reply(
        ticket_id, ADMIN_CHAT, "Переустановите приложение",
        [("fix.jpg", "image/jpeg", b"\xff\xd8\xff\xe0")],
    )

    assert await _status(ticket_id) == "answered"
    [pending] = await support.pending_operator_replies()
    assert pending["id"] == reply_id
    assert pending["ticket_id"] == ticket_id
    assert pending["body"] == "Переустановите приложение"
    assert pending["attachment_count"] == 1
    thread = await support.thread(ticket_id)
    assert [message["author"] for message in thread] == ["user", "admin"]
    assert thread[1]["admin_telegram_id"] == ADMIN_CHAT
    assert thread[1]["attachments"][0]["file_name"] == "fix.jpg"


async def test_answering_a_ticket_the_customer_closed_reopens_it():
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id)
    await _close_as_customer(ticket_id)

    await support.add_admin_reply(ticket_id, ADMIN_CHAT, "Ещё одно")

    assert await _status(ticket_id) == "answered"
    # And a later close is announced again rather than being taken as known.
    await support.mark_close_announced(ticket_id)
    await support.add_admin_reply(ticket_id, ADMIN_CHAT, "И ещё")
    await _close_as_customer(ticket_id)
    assert [row["id"] for row in await support.pending_close_announcements()] == [ticket_id]


async def test_answering_a_ticket_that_does_not_exist_writes_nothing():
    assert await support.add_admin_reply(424242, ADMIN_CHAT, "Ответ") is None
    assert await support.pending_operator_replies() == []


async def test_close_and_reopen_report_whether_they_changed_anything():
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id)

    assert await support.close(ticket_id) is True
    assert await support.close(ticket_id) is False
    assert await _status(ticket_id) == "closed"

    assert await support.reopen(ticket_id) is True
    assert await support.reopen(ticket_id) is False
    assert await _status(ticket_id) == "open"


async def test_only_a_close_by_the_customer_is_announced():
    user_id = await _customer()
    by_customer, _ = await _ticket(user_id, subject="first")
    by_operator, _ = await _ticket(user_id, subject="second")
    await _close_as_customer(by_customer)
    await support.close(by_operator)

    pending = await support.pending_close_announcements()
    assert [row["id"] for row in pending] == [by_customer]

    await support.mark_close_announced(by_customer)
    assert await support.pending_close_announcements() == []


async def test_the_queue_holds_only_tickets_waiting_on_us_oldest_first():
    user_id = await _customer()
    older, _ = await _ticket(user_id, subject="older")
    newer, _ = await _ticket(user_id, subject="newer")
    answered, _ = await _ticket(user_id, subject="answered")
    await support.add_admin_reply(answered, ADMIN_CHAT, "Ответ")
    pool = await get_pool()
    await pool.execute(
        "UPDATE support_tickets SET updated_at = now() - interval '1 hour' WHERE id = $1", older
    )

    assert await support.count_waiting() == 2
    page = await support.waiting_page(10, 0)
    assert [row["id"] for row in page] == [older, newer]
    assert page[0]["email"] == "customer@example.com"


async def test_a_fresh_card_shows_what_the_customer_said_last():
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id, body="first")
    await support.add_admin_reply(ticket_id, ADMIN_CHAT, "answer")
    await _customer_message(ticket_id, "latest", [("log.txt", "text/plain", b"log")])

    latest = await support.latest_customer_message(ticket_id)

    assert latest["body"] == "latest"
    assert latest["attachments"][0]["file_name"] == "log.txt"


async def test_a_purged_file_has_no_bytes_left_to_send():
    user_id = await _customer()
    await _ticket(user_id, files=[("clip.mp4", "video/mp4", b"....ftypisom")])
    [pending] = await support.pending_customer_messages()
    attachment_id = pending["attachments"][0]["id"]

    assert await support.attachment_data(attachment_id) == b"....ftypisom"

    pool = await get_pool()
    await pool.execute(
        "DELETE FROM support_attachment_data WHERE attachment_id = $1::uuid", attachment_id
    )
    assert await support.attachment_data(attachment_id) is None
    [pending] = await support.pending_customer_messages()
    assert pending["attachments"][0]["purged"] is True


# -- the account the tickets belong to ------------------------------------------


async def test_linking_telegram_carries_the_tickets_over_to_the_survivor():
    """
    A session on the absorbed row resolves to the survivor after a merge, and
    the site lists tickets by the survivor's id. Left behind, they would
    disappear from the cabinet the moment the customer linked Telegram.
    """
    now = int(time.time())
    web_id = await _customer("merge@example.com")
    ticket_id, _ = await _ticket(web_id)
    await users.create_user_record(9001, "tg_user")
    telegram_row = await users.get_user_by_id(9001)
    web_row = await users.get_user_by_uuid(web_id)

    await users.apply_merge(plan_merge(survivor=dict(telegram_row), absorbed=dict(web_row), now=now))

    ticket = await support.get_ticket(ticket_id)
    assert ticket["user_id"] == str(telegram_row["id"])
    assert ticket["telegram_id"] == 9001


async def test_deleting_a_customer_takes_their_tickets_with_them():
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id, files=[("a.png", "image/png", b"\x89PNG")])

    assert await users.delete_user_row(user_id) is True

    assert await support.get_ticket(ticket_id) is None
    assert await support.pending_customer_messages() == []


@pytest.mark.parametrize("status", ["open", "answered", "closed"])
async def test_every_status_the_site_writes_is_accepted(status):
    user_id = await _customer()
    ticket_id, _ = await _ticket(user_id)
    pool = await get_pool()
    await pool.execute("UPDATE support_tickets SET status = $2 WHERE id = $1", ticket_id, status)
    assert await _status(ticket_id) == status

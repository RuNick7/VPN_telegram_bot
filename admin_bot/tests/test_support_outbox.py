"""
Delivery of support tickets between the website and Telegram.

The properties pinned here are the ones whose failure is silent: a message
that never reaches an operator, a follow-up that lands before its card, a
file Telegram refuses that then blocks every ticket behind it, a pass that
dies halfway and either loses the rest or sends everything twice.
"""

from types import SimpleNamespace

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.methods import SendMessage

from app.scheduler.jobs import support_outbox

METHOD = SendMessage(chat_id=1, text="x")
ADMIN, OTHER = 111, 222


class FakeSupport:
    """The repository, in memory, holding exactly what the outbox reads and writes."""

    def __init__(self):
        self.messages: list[dict] = []
        self.data: dict[str, bytes] = {}
        self.telegram: list[dict] = []
        self.delivered: list[int] = []
        self.failures: list[tuple[int, str]] = []
        self.closed: list[dict] = []
        self.announced: list[int] = []
        self.replies: list[dict] = []

    async def pending_customer_messages(self):
        return [m for m in self.messages if m["id"] not in self.delivered]

    async def delivered_parts(self, support_message_id):
        parts = {}
        for row in sorted(self.telegram, key=lambda r: r["telegram_message_id"]):
            if row["support_message_id"] == support_message_id:
                parts.setdefault((row["chat_id"], row["attachment_id"]), row["telegram_message_id"])
        return parts

    async def record_telegram_message(self, chat_id, telegram_message_id, ticket_id, kind,
                                      *, support_message_id=None, attachment_id=None):
        self.telegram.append(dict(
            chat_id=chat_id, telegram_message_id=telegram_message_id, ticket_id=ticket_id,
            kind=kind, support_message_id=support_message_id, attachment_id=attachment_id,
        ))

    async def card_for(self, ticket_id, chat_id):
        cards = [r for r in self.telegram if r["ticket_id"] == ticket_id and r["chat_id"] == chat_id
                 and r["kind"] == "card"]
        return cards[-1]["telegram_message_id"] if cards else None

    async def attachment_data(self, attachment_id):
        return self.data.get(attachment_id)

    async def mark_delivered(self, *ids):
        self.delivered.extend(ids)

    async def record_delivery_failure(self, message_id, error):
        self.failures.append((message_id, error))
        return len(self.failures)

    async def pending_close_announcements(self):
        return [t for t in self.closed if t["id"] not in self.announced]

    async def mark_close_announced(self, ticket_id):
        self.announced.append(ticket_id)

    async def pending_operator_replies(self):
        return [r for r in self.replies if r["id"] not in self.delivered]

    def sent_to(self, chat_id, kind=None):
        return [r for r in self.telegram if r["chat_id"] == chat_id and (kind is None or r["kind"] == kind)]


class FakeBot:
    """Records every send; `fail` decides which ones raise, and with what."""

    def __init__(self):
        self.calls: list[dict] = []
        self.next_id = 1000
        self.fail = lambda call: None

    async def _send(self, method, chat_id, **kwargs):
        call = {"method": method, "chat_id": chat_id, **kwargs}
        error = self.fail(call)
        if error is not None:
            raise error
        self.next_id += 1
        call["message_id"] = self.next_id
        self.calls.append(call)
        return SimpleNamespace(message_id=self.next_id, chat=SimpleNamespace(id=chat_id))

    async def send_message(self, chat_id, text, **kwargs):
        return await self._send("message", chat_id, text=text, **kwargs)

    async def send_photo(self, chat_id, photo, **kwargs):
        return await self._send("photo", chat_id, file=photo, **kwargs)

    async def send_video(self, chat_id, video, **kwargs):
        return await self._send("video", chat_id, file=video, **kwargs)

    async def send_document(self, chat_id, document, **kwargs):
        return await self._send("document", chat_id, file=document, **kwargs)

    def to(self, chat_id):
        return [c for c in self.calls if c["chat_id"] == chat_id]


@pytest.fixture
def support(monkeypatch):
    fake = FakeSupport()
    monkeypatch.setattr(support_outbox, "_support", fake)
    monkeypatch.setattr(support_outbox.settings, "admin_ids_raw", f"{ADMIN} {OTHER}")
    return fake


@pytest.fixture
def bot():
    return FakeBot()


def ticket_message(message_id=1, ticket_id=7, *, opens=True, body="Не подключается", files=()):
    return dict(
        id=message_id, ticket_id=ticket_id, body=body, created_at=0, delivery_attempts=0,
        subject="Тема", status="open", opens_ticket=opens, user_id="u-1",
        email="customer@example.com", telegram_id=None, telegram_tag="", subscription_ends=0,
        attachments=[
            dict(id=f"file-{message_id}-{i}", message_id=message_id, file_name=name,
                 content_type=content_type, size_bytes=1000, purged=False)
            for i, (name, content_type) in enumerate(files)
        ],
    )


def add(support, message, content=b"data"):
    support.messages.append(message)
    for attachment in message["attachments"]:
        support.data[attachment["id"]] = content


# -- customer -> operators ---------------------------------------------------------------


async def test_a_new_ticket_reaches_every_operator_as_a_card_with_its_files(support, bot):
    add(support, ticket_message(files=[("a.png", "image/png"), ("b.mov", "video/quicktime")]))

    await support_outbox.run_pass(bot)

    for chat in (ADMIN, OTHER):
        card, photo, video = bot.to(chat)
        assert card["method"] == "message" and "Обращение #7" in card["text"]
        assert card["reply_markup"] is not None, "the card carries the ticket's buttons"
        # The files thread onto the card, so they read as part of it.
        assert photo["method"] == "photo" and photo["reply_parameters"].message_id == card["message_id"]
        assert video["method"] == "document"  # QuickTime is not a Telegram video
        assert [r["kind"] for r in support.sent_to(chat)] == ["card", "attachment", "attachment"]
    assert support.delivered == [1]


async def test_a_follow_up_replies_to_the_card_in_each_chat(support, bot):
    add(support, ticket_message(1))
    await support_outbox.run_pass(bot)
    add(support, ticket_message(2, opens=False, body="Ещё деталь"))

    await support_outbox.run_pass(bot)

    for chat in (ADMIN, OTHER):
        card, follow_up = bot.to(chat)
        assert "Ещё деталь" in follow_up["text"]
        assert follow_up["reply_parameters"].message_id == card["message_id"]


async def test_one_operator_who_blocked_the_bot_does_not_stop_the_others(support, bot):
    add(support, ticket_message())
    bot.fail = lambda call: (
        TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user")
        if call["chat_id"] == OTHER else None
    )

    await support_outbox.run_pass(bot)

    assert len(bot.to(ADMIN)) == 1
    assert support.delivered == [1]
    assert support.failures == []


async def test_a_ticket_nobody_could_receive_stays_queued(support, bot):
    # Skipping one admin who blocked the bot is right. Skipping every one of
    # them and calling the ticket delivered would lose it silently.
    add(support, ticket_message())
    bot.fail = lambda call: TelegramForbiddenError(METHOD, "Forbidden: bot can't initiate conversation")

    with pytest.raises(support_outbox.NobodyToDeliverTo):
        await support_outbox.run_pass(bot)

    assert support.delivered == []
    assert "Start" in support.failures[0][1]


async def test_a_pass_that_dies_halfway_resends_only_what_did_not_arrive(support, bot):
    add(support, ticket_message(files=[("a.png", "image/png"), ("b.pdf", "application/pdf")]))
    bot.fail = lambda call: (
        TelegramNetworkError(METHOD, "timeout") if call["method"] == "document" else None
    )

    with pytest.raises(TelegramNetworkError):
        await support_outbox.run_pass(bot)
    assert support.delivered == []
    assert support.failures and support.failures[0][0] == 1

    bot.fail = lambda call: None
    await support_outbox.run_pass(bot)

    methods = [c["method"] for c in bot.to(ADMIN)]
    assert methods == ["message", "photo", "document"], "the card and the photo were not sent twice"
    assert support.delivered == [1]


async def test_a_file_telegram_refuses_is_replaced_by_a_note_and_the_queue_moves_on(support, bot):
    add(support, ticket_message(1, files=[("huge.mp4", "video/mp4")]))
    add(support, ticket_message(2, ticket_id=8))
    bot.fail = lambda call: (
        TelegramEntityTooLarge(METHOD, "Request Entity Too Large") if call["method"] in ("video", "document") else None
    )

    await support_outbox.run_pass(bot)

    card, note, _next_card = bot.to(ADMIN)
    assert "не принял файл «huge.mp4»" in note["text"]
    assert support.delivered == [1, 2]
    # And the note stands for the file, so it is never tried again.
    assert (ADMIN, "file-1-0") in await support.delivered_parts(1)


async def test_a_photo_telegram_will_not_take_as_a_photo_goes_as_a_document(support, bot):
    add(support, ticket_message(files=[("long-screenshot.png", "image/png")]))
    bot.fail = lambda call: (
        TelegramBadRequest(METHOD, "Bad Request: PHOTO_INVALID_DIMENSIONS") if call["method"] == "photo" else None
    )

    await support_outbox.run_pass(bot)

    assert [c["method"] for c in bot.to(ADMIN)] == ["message", "document"]


async def test_a_long_text_is_recorded_only_once_all_of_it_is_out(support, bot):
    message = ticket_message(body="слово " * 1500)
    add(support, message)
    parts_in_full = len(support_outbox.card_messages(message, 0))
    assert parts_in_full > 2
    sends = {"n": 0}

    def fail_second_part(call):
        if call["chat_id"] == ADMIN and call["method"] == "message":
            sends["n"] += 1
            if sends["n"] == 2:
                return TelegramNetworkError(METHOD, "timeout")
        return None

    bot.fail = fail_second_part
    with pytest.raises(TelegramNetworkError):
        await support_outbox.run_pass(bot)
    # Recording the first part here would have marked the text done, and the
    # second part would never have been sent.
    assert support.sent_to(ADMIN) == []

    await support_outbox.run_pass(bot)
    parts = [c for c in bot.to(ADMIN) if c["method"] == "message"]
    # The first part twice -- a repeat, never a loss.
    assert len(parts) == 1 + parts_in_full
    assert "Ответьте на это сообщение" in parts[-1]["text"]
    assert len(support.sent_to(ADMIN)) == parts_in_full


async def test_a_file_already_purged_is_named_instead_of_sent(support, bot):
    message = ticket_message(files=[("old.png", "image/png")])
    message["attachments"][0]["purged"] = True
    support.messages.append(message)

    await support_outbox.run_pass(bot)

    card, note = bot.to(ADMIN)
    assert "удалён по сроку" in note["text"]


async def test_a_customer_closing_a_ticket_is_announced_on_its_card(support, bot):
    add(support, ticket_message())
    await support_outbox.run_pass(bot)
    support.closed.append({"id": 7, "subject": "Тема"})

    await support_outbox.run_pass(bot)

    card, notice = bot.to(ADMIN)
    assert "Клиент закрыл обращение" in notice["text"]
    assert notice["reply_parameters"].message_id == card["message_id"]
    assert support.announced == [7]


# -- operators -> customer ------------------------------------------------------------------


@pytest.fixture
def notified(monkeypatch, support):
    calls = []

    async def notify(telegram_id, ticket_id, replies):
        calls.append((telegram_id, ticket_id, [r["id"] for r in replies]))

    monkeypatch.setattr(support_outbox, "_notify_customer", notify)
    monkeypatch.setattr(support_outbox.settings, "user_bot_token", "123:TEST")
    return calls


def reply(reply_id, ticket_id=7, telegram_id=555):
    return dict(id=reply_id, ticket_id=ticket_id, body="Ответ", subject="Тема",
                telegram_id=telegram_id, attachment_count=0)


async def test_several_answers_to_one_ticket_make_one_notification(support, notified):
    support.replies += [reply(1), reply(2), reply(3, ticket_id=8)]

    await support_outbox.notify_customers()

    assert notified == [(555, 7, [1, 2]), (555, 8, [3])]
    assert sorted(support.delivered) == [1, 2, 3]


async def test_a_customer_without_telegram_is_settled_without_a_message(support, notified):
    support.replies.append(reply(1, telegram_id=None))

    await support_outbox.notify_customers()

    assert notified == []
    assert support.delivered == [1]


async def test_a_customer_who_blocked_the_bot_is_not_retried_forever(support, monkeypatch):
    async def blocked(*args):
        raise TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user")

    monkeypatch.setattr(support_outbox, "_notify_customer", blocked)
    monkeypatch.setattr(support_outbox.settings, "user_bot_token", "123:TEST")
    support.replies.append(reply(1))

    await support_outbox.notify_customers()

    assert support.delivered == [1]


async def test_a_temporary_failure_leaves_the_answer_to_be_announced_later(support, monkeypatch):
    async def down(*args):
        raise TelegramNetworkError(METHOD, "timeout")

    monkeypatch.setattr(support_outbox, "_notify_customer", down)
    monkeypatch.setattr(support_outbox.settings, "user_bot_token", "123:TEST")
    support.replies.append(reply(1))

    with pytest.raises(TelegramNetworkError):
        await support_outbox.notify_customers()
    assert support.delivered == []
    assert support.failures[0][0] == 1


def test_the_button_only_points_at_a_site_a_phone_can_open(monkeypatch):
    monkeypatch.setattr(support_outbox.settings, "web_base_url", "https://kairavpn.pro/")
    assert support_outbox._ticket_url(7) == "https://kairavpn.pro/app/support?id=7"
    monkeypatch.setattr(support_outbox.settings, "web_base_url", "http://localhost:8080")
    assert support_outbox._ticket_url(7) == ""


# -- the loop ------------------------------------------------------------------------------


async def test_the_loop_survives_a_failed_pass_and_records_it(monkeypatch):
    recorded = []

    async def failing_pass(bot):
        raise RuntimeError("database is down")

    async def record(**kwargs):
        recorded.append(kwargs)

    async def stop(_delay):
        raise KeyboardInterrupt  # out of the infinite loop, after one lap

    monkeypatch.setattr(support_outbox, "run_pass", failing_pass)
    monkeypatch.setattr(support_outbox, "_record", record)
    monkeypatch.setattr(support_outbox.asyncio, "sleep", stop)

    with pytest.raises(KeyboardInterrupt):
        await support_outbox.run_support_outbox(FakeBot())

    assert recorded == [{"failure": "database is down"}]

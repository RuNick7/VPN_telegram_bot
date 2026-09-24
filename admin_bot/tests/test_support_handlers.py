"""
How an operator answers a ticket from Telegram.

The mechanism is a reply, so the questions worth pinning are the ones about
replies: which ones count as an answer, what of an answer reaches the
customer, and that nobody but an admin gets to the handler at all.
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Document, Message, PhotoSize, Update, User, Voice

from app.handlers.admin import router as admin_router
from app.handlers.admin import support
from app.middlewares import AdminAccessMiddleware

ADMIN = User(id=111, is_bot=False, first_name="Анна", username="anna_ops")
OTHER_ADMIN_CHAT = 222
CHAT = Chat(id=111, type="private")


def card(message_id=500) -> Message:
    return Message(message_id=message_id, date=0, chat=CHAT, text="🆘 Обращение #7")


def reply(**kwargs) -> Message:
    message = Message(message_id=900, date=0, chat=CHAT, from_user=ADMIN, reply_to_message=card(), **kwargs)
    object.__setattr__(message, "reply", AsyncMock(return_value=SimpleNamespace(message_id=901)))
    return message


class FakeBot:
    def __init__(self, content=b"file-bytes"):
        self.content = content
        self.downloaded = []
        self.sent = []

    async def download(self, file_id, timeout=30):
        self.downloaded.append(file_id)
        return BytesIO(self.content)

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(message_id=950, chat=SimpleNamespace(id=chat_id))


# -- which replies are answers --------------------------------------------------------------


async def test_a_reply_to_a_ticket_message_carries_the_ticket(monkeypatch):
    monkeypatch.setattr(support._support, "ticket_for_telegram_message", AsyncMock(return_value=7))
    assert await support.TicketReply()(reply(text="Ответ")) == {"ticket_id": 7}


async def test_a_reply_to_anything_else_is_not_an_answer(monkeypatch):
    monkeypatch.setattr(support._support, "ticket_for_telegram_message", AsyncMock(return_value=None))
    assert await support.TicketReply()(reply(text="Ответ")) is False

    lookup = AsyncMock()
    monkeypatch.setattr(support._support, "ticket_for_telegram_message", lookup)
    plain = Message(message_id=1, date=0, chat=CHAT, from_user=ADMIN, text="/admin")
    assert await support.TicketReply()(plain) is False
    lookup.assert_not_awaited()  # no query for a message that is not a reply


async def test_a_command_typed_in_reply_to_a_card_stays_a_command(monkeypatch):
    lookup = AsyncMock(return_value=7)
    monkeypatch.setattr(support._support, "ticket_for_telegram_message", lookup)
    assert await support.TicketReply()(reply(text="/tickets")) is False
    lookup.assert_not_awaited()


async def test_a_strangers_reply_never_reaches_the_answer_handler():
    """
    Through a real dispatcher rather than by inspecting the router tree: even
    if a stranger's reply somehow matched a ticket, the admin check has to
    stop it before anything is written.
    """
    dp = Dispatcher()
    dp.include_router(admin_router)
    bot = Bot(token="123456:TEST")
    stranger_chat = Chat(id=999, type="private")
    stranger = User(id=999, is_bot=False, first_name="Stranger")
    update = Update(update_id=1, message=Message(
        message_id=11, date=0, chat=stranger_chat, from_user=stranger, text="ответ",
        reply_to_message=Message(message_id=10, date=0, chat=stranger_chat, text="карточка"),
    ))
    answer_read = AsyncMock()
    try:
        with patch.object(support._support, "ticket_for_telegram_message", AsyncMock(return_value=7)), \
             patch("app.middlewares.admin_auth.check_admin_access", AsyncMock(return_value=False)), \
             patch.object(support, "read_answer", answer_read), \
             patch.object(Message, "answer", AsyncMock()) as denied:
            await dp.feed_update(bot, update)
    finally:
        await bot.session.close()

    answer_read.assert_not_awaited()
    denied.assert_awaited_once()


def test_support_sits_first_under_the_admin_check():
    # Under the admin router, it inherits the middleware -- a stranger's
    # reply never reaches answer_ticket. First, so a reply is an answer even
    # mid-way through another admin form.
    assert admin_router.sub_routers[0] is support.router
    assert any(isinstance(m, AdminAccessMiddleware) for m in admin_router.message.middleware)
    assert any(isinstance(m, AdminAccessMiddleware) for m in admin_router.callback_query.middleware)


# -- what of an answer is passed on -------------------------------------------------------


async def test_a_photo_is_taken_at_its_largest(monkeypatch):
    bot = FakeBot()
    message = reply(
        caption="Вот так должно быть",
        photo=[
            PhotoSize(file_id="small", file_unique_id="s", width=90, height=90, file_size=1_000),
            PhotoSize(file_id="large", file_unique_id="l", width=1280, height=1280, file_size=90_000),
        ],
    )

    body, files = await support.read_answer(message, bot)

    assert body == "Вот так должно быть"
    assert bot.downloaded == ["large"]
    assert files == [("photo_900.jpg", "image/jpeg", b"file-bytes")]


async def test_a_document_keeps_its_name_but_not_its_path():
    message = reply(document=Document(
        file_id="doc", file_unique_id="d", file_name="../../инструкция.pdf",
        mime_type="application/pdf", file_size=2_000,
    ))
    _, files = await support.read_answer(message, FakeBot())
    assert files[0][:2] == ("инструкция.pdf", "application/pdf")


async def test_a_file_the_bot_cannot_download_is_refused_with_a_reason():
    message = reply(document=Document(file_id="big", file_unique_id="b", file_name="dump.zip",
                                      file_size=21 * 1024 * 1024))
    with pytest.raises(support.AnswerRefused, match="20 МБ"):
        await support.read_answer(message, FakeBot())


async def test_a_voice_message_is_refused_rather_than_lost():
    message = reply(voice=Voice(file_id="v", file_unique_id="v", duration=3))
    with pytest.raises(support.AnswerRefused, match="текстом, фото, видео или файлом"):
        await support.read_answer(message, FakeBot())


# -- answering ----------------------------------------------------------------------------


@pytest.fixture
def ticket_store(monkeypatch):
    store = SimpleNamespace(
        get_ticket=AsyncMock(return_value={"id": 7, "telegram_id": 555, "status": "open"}),
        add_admin_reply=AsyncMock(return_value=42),
        record_telegram_message=AsyncMock(),
        card_for=AsyncMock(return_value=800),
    )
    monkeypatch.setattr(support, "_support", store)
    monkeypatch.setattr(support.settings, "admin_ids_raw", f"{ADMIN.id} {OTHER_ADMIN_CHAT}")
    return store


async def test_an_answer_is_stored_confirmed_and_shown_to_the_other_operator(ticket_store):
    bot = FakeBot()
    message = reply(text="Сбросьте ссылку в разделе «Устройства».")

    await support.answer_ticket(message, bot, ticket_id=7)

    ticket_store.add_admin_reply.assert_awaited_once_with(7, ADMIN.id, "Сбросьте ссылку в разделе «Устройства».", [])
    confirmation = message.reply.await_args.args[0]
    assert "#7" in confirmation and "уведомление в Telegram" in confirmation
    # The answer and the confirmation both lead back to the ticket when replied to.
    recorded = [call.args[1] for call in ticket_store.record_telegram_message.await_args_list]
    assert 900 in recorded and 901 in recorded
    [(chat_id, text, kwargs)] = bot.sent
    assert chat_id == OTHER_ADMIN_CHAT
    assert "@anna_ops ответил" in text and kwargs["reply_parameters"].message_id == 800


async def test_a_customer_without_telegram_is_said_to_see_it_on_the_site(ticket_store):
    ticket_store.get_ticket.return_value = {"id": 7, "telegram_id": None, "status": "open"}
    message = reply(text="Ответ")

    await support.answer_ticket(message, FakeBot(), ticket_id=7)

    assert "в личном кабинете" in message.reply.await_args.args[0]


async def test_an_answer_to_a_ticket_that_is_gone_says_so(ticket_store):
    ticket_store.get_ticket.return_value = None
    message = reply(text="Ответ")

    await support.answer_ticket(message, FakeBot(), ticket_id=7)

    ticket_store.add_admin_reply.assert_not_awaited()
    assert "больше нет" in message.reply.await_args.args[0]


async def test_the_customers_own_words_in_an_operator_notice_are_escaped(ticket_store):
    bot = FakeBot()
    await support.answer_ticket(reply(text="<b>жирный</b>"), bot, ticket_id=7)
    assert "&lt;b&gt;" in bot.sent[0][1]


# -- buttons ----------------------------------------------------------------------------------


def pressed(data: str) -> CallbackQuery:
    callback = CallbackQuery(id="1", from_user=ADMIN, chat_instance="ci", data=data, message=card())
    object.__setattr__(callback, "answer", AsyncMock())
    object.__setattr__(callback.message, "edit_reply_markup", AsyncMock())
    return callback


async def test_closing_swaps_the_button_for_reopening(monkeypatch):
    monkeypatch.setattr(support._support, "close", AsyncMock(return_value=True))
    callback = pressed("support:close:7")

    await support.close_ticket(callback)

    support._support.close.assert_awaited_once_with(7)
    assert "закрыто" in callback.answer.await_args.args[0]
    keyboard = callback.message.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "support:reopen:7"


async def test_reopening_puts_the_close_button_back(monkeypatch):
    monkeypatch.setattr(support._support, "reopen", AsyncMock(return_value=False))
    callback = pressed("support:reopen:7")

    await support.reopen_ticket(callback)

    assert "и так открыто" in callback.answer.await_args.args[0]
    keyboard = callback.message.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "support:close:7"


# -- the queue ---------------------------------------------------------------------------------


def test_the_queue_says_who_has_waited_and_escapes_what_they_wrote():
    text = support.format_queue(
        [{"id": 7, "subject": "<нет связи>", "email": "a@b.c", "telegram_tag": "", "updated_at": 0}],
        page=1, total=1, now=3 * 3600,
    )
    assert "#7" in text and "&lt;нет связи&gt;" in text
    assert "ждёт 3 ч" in text


def test_a_long_subject_is_shortened_on_its_button():
    label = support.queue_label({"id": 7, "subject": "а" * 80})
    assert label.startswith("#7 · ") and label.endswith("…") and len(label) < 64


async def test_an_empty_queue_says_everything_is_answered(monkeypatch):
    monkeypatch.setattr(support._support, "count_waiting", AsyncMock(return_value=0))
    target = SimpleNamespace(answer=AsyncMock())

    await support.render_queue(target, 1, support.PAGE_SIZE, edit=False)

    assert "Все обращения отвечены" in target.answer.await_args.args[0]


async def test_the_queue_is_not_offered_while_support_is_off(monkeypatch):
    monkeypatch.setattr(support.settings, "support_enabled", False)
    target = SimpleNamespace(answer=AsyncMock())

    await support._show_queue(target)

    assert "SUPPORT_ENABLED" in target.answer.await_args.args[0]

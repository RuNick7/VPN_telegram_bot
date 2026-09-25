"""
Operators answer support tickets from Telegram.

A ticket arrives as a card (see `scheduler/jobs/support_outbox.py`). To answer
it, an operator replies -- to the card, or to anything else that belongs to
the ticket: a follow-up, one of the customer's files, a notice, their own
earlier answer. Text, a photo, a video or a document with a caption all work;
a file is downloaded from Telegram and stored with the answer, so the
customer sees it in the cabinet.

This router is included first in the admin router, and the reply handler has
no state filter, so a reply to a ticket is taken as an answer even while some
other admin form is half filled in. Replying to a card is as deliberate as
an action in this bot gets.

Authorization comes from the admin router's middleware, like every handler
below it: only an admin's reply reaches `answer_ticket`.
"""

from __future__ import annotations

import logging
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from tgvpn_shared.db import SupportRepository

from app.config.settings import settings
from app.handlers.admin.pagination import (
    MENU_BUTTON,
    PagedView,
    parse_page,
    picker_keyboard,
    prompt_page_input,
    register_view,
)
from app.handlers.admin.users.common import find_db_row, find_panel_user
from app.handlers.admin.users.search import build_report
from app.services.support import (
    clean_name,
    escape,
    fresh_card,
    history_messages,
    reply_to,
    ticket_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_support")

_support = SupportRepository()

# The Bot API will not let a bot download anything larger.
DOWNLOAD_LIMIT = 20 * 1024 * 1024

PAGE_SIZE = 8
LIST_PREFIX = "support:list"
LIST_GOTO = "support:list:goto"


class AnswerRefused(Exception):
    """An answer that cannot be passed on as it is. The text is for the operator."""


class TicketReply(BaseFilter):
    """
    A reply to a message that belongs to a ticket. Hands the ticket's id to
    the handler, so it never has to be looked up twice.
    """

    async def __call__(self, message: Message) -> bool | dict:
        replied = message.reply_to_message
        if replied is None:
            return False
        # A command typed while a reply to a card is still selected is a
        # command. Sent to the customer as an answer, "/tickets" would be a
        # message they could make no sense of.
        if (message.text or "").startswith("/"):
            return False
        ticket_id = await _support.ticket_for_telegram_message(message.chat.id, replied.message_id)
        return {"ticket_id": int(ticket_id)} if ticket_id else False


def _media_of(message: Message) -> tuple[str, str, str, int | None] | None:
    """(file_id, name, content type, size) of an answer's file, if it has one."""
    if message.photo:
        photo = message.photo[-1]  # the largest size Telegram kept
        return photo.file_id, f"photo_{message.message_id}.jpg", "image/jpeg", photo.file_size
    if message.video:
        video = message.video
        name = clean_name(video.file_name, f"video_{message.message_id}.mp4")
        return video.file_id, name, video.mime_type or "video/mp4", video.file_size
    # Before the document: a GIF arrives as both, and is played as a video.
    if message.animation:
        animation = message.animation
        name = clean_name(animation.file_name, f"animation_{message.message_id}.mp4")
        return animation.file_id, name, animation.mime_type or "video/mp4", animation.file_size
    if message.document:
        document = message.document
        name = clean_name(document.file_name, f"file_{message.message_id}")
        return document.file_id, name, document.mime_type or "application/octet-stream", document.file_size
    return None


async def read_answer(message: Message, bot: Bot) -> tuple[str, list[tuple[str, str, bytes]]]:
    """The text and the file of an operator's answer, ready to store."""
    body = (message.text or message.caption or "").strip()
    media = _media_of(message)
    if media is None:
        if message.text is None and message.caption is None:
            raise AnswerRefused(
                "Такое сообщение клиенту не передать. Ответьте текстом, фото, видео или файлом."
            )
        return body, []

    file_id, name, content_type, size = media
    if size and size > DOWNLOAD_LIMIT:
        raise AnswerRefused(
            "Файл больше 20 МБ — бот не может его скачать, а значит и передать клиенту. "
            "Сожмите его или пришлите ссылкой."
        )
    downloaded = await bot.download(file_id, timeout=120)
    return body, [(name, content_type, downloaded.read())]


@router.message(TicketReply())
async def answer_ticket(message: Message, bot: Bot, ticket_id: int) -> None:
    try:
        body, files = await read_answer(message, bot)
    except AnswerRefused as exc:
        await message.reply(f"⚠️ {exc}")
        return
    except Exception as exc:
        logger.error("Could not read an answer to #%s: %s", ticket_id, exc, exc_info=True)
        await message.reply(f"❌ Не удалось получить файл из Telegram: {escape(exc)}. Попробуйте ещё раз.")
        return
    if not body and not files:
        await message.reply("⚠️ Пустой ответ не отправлен.")
        return

    ticket = await _support.get_ticket(ticket_id)
    reply_id = await _support.add_admin_reply(ticket_id, message.from_user.id, body, files) if ticket else None
    if reply_id is None:
        await message.reply(f"❌ Обращения #{ticket_id} больше нет — возможно, клиента удалили.")
        return

    # The answer itself belongs to the ticket too: replying to it again is
    # the natural way to add something.
    await _support.record_telegram_message(
        message.chat.id, message.message_id, ticket_id, "notice", support_message_id=reply_id
    )
    where = (
        "Клиенту придёт уведомление в Telegram."
        if ticket["telegram_id"]
        else "Клиент увидит ответ в личном кабинете."
    )
    confirmation = await message.reply(
        f"✅ Ответ отправлен в обращение <b>#{ticket_id}</b>. {where}",
        reply_markup=ticket_keyboard(ticket_id),
    )
    await _support.record_telegram_message(message.chat.id, confirmation.message_id, ticket_id, "notice")
    await tell_other_operators(bot, message, ticket_id, body, len(files))


async def tell_other_operators(bot: Bot, message: Message, ticket_id: int, body: str, files: int) -> None:
    """
    Show the answer to the other operators who have this ticket, so the same
    question is not answered twice. Best effort: the answer is already saved.
    """
    author = message.from_user
    name = f"@{author.username}" if author.username else author.full_name
    text = f"💬 {escape(name)} ответил в <b>#{ticket_id}</b>:\n\n{escape(body[:1500])}"
    if files:
        text += "\n📎 с файлом"
    for chat_id in settings.admin_ids:
        if chat_id == message.chat.id:
            continue
        card = await _support.card_for(ticket_id, chat_id)
        if card is None:
            continue  # this operator never had the ticket
        try:
            sent = await bot.send_message(chat_id, text, reply_parameters=reply_to(card))
            await _support.record_telegram_message(chat_id, sent.message_id, ticket_id, "notice")
        except Exception as exc:
            logger.warning("Could not show the answer to #%s in chat %s: %s", ticket_id, chat_id, exc)


# -- buttons under a card -----------------------------------------------------------


def _ticket_id(callback: CallbackQuery) -> int:
    tail = (callback.data or "").rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else 0


async def _swap_keyboard(callback: CallbackQuery, keyboard: InlineKeyboardMarkup) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except (TelegramBadRequest, AttributeError):
        # Too old to edit, or unchanged. The toast already said what happened.
        pass


@router.callback_query(F.data.startswith("support:close:"))
async def close_ticket(callback: CallbackQuery) -> None:
    ticket_id = _ticket_id(callback)
    changed = await _support.close(ticket_id)
    await callback.answer(f"Обращение #{ticket_id} закрыто." if changed else "Оно уже закрыто.")
    await _swap_keyboard(callback, ticket_keyboard(ticket_id, closed=True))


@router.callback_query(F.data.startswith("support:reopen:"))
async def reopen_ticket(callback: CallbackQuery) -> None:
    ticket_id = _ticket_id(callback)
    changed = await _support.reopen(ticket_id)
    await callback.answer(f"Обращение #{ticket_id} снова открыто." if changed else "Оно и так открыто.")
    await _swap_keyboard(callback, ticket_keyboard(ticket_id))


@router.callback_query(F.data.startswith("support:client:"))
async def show_client(callback: CallbackQuery) -> None:
    """The same card the user search shows, for the person behind the ticket."""
    ticket = await _support.get_ticket(_ticket_id(callback))
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    await callback.answer()
    needle = ticket["user_id"]
    row = await find_db_row(needle)
    panel_user = None
    try:
        panel_user, _ = await find_panel_user(needle, row)
    except Exception as exc:
        await callback.message.answer(f"⚠️ Ошибка запроса к Remnawave: {escape(exc)}")
    await callback.message.answer(build_report(needle, panel_user, [row] if row else []), parse_mode="HTML")


@router.callback_query(F.data.startswith("support:history:"))
async def show_history(callback: CallbackQuery) -> None:
    ticket_id = _ticket_id(callback)
    ticket = await _support.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    await callback.answer()
    for text in history_messages(ticket, await _support.thread(ticket_id)):
        sent = await callback.message.answer(text)
        await _support.record_telegram_message(sent.chat.id, sent.message_id, ticket_id, "notice")


@router.callback_query(F.data.startswith("support:open:"))
async def open_ticket(callback: CallbackQuery) -> None:
    """A fresh card from the list -- one an answer can reply to."""
    ticket_id = _ticket_id(callback)
    ticket = await _support.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    await callback.answer()
    latest = await _support.latest_customer_message(ticket_id)
    sent = await callback.message.answer(
        fresh_card(ticket, latest, int(time.time())),
        reply_markup=ticket_keyboard(ticket_id, closed=ticket["status"] == "closed"),
    )
    await _support.record_telegram_message(sent.chat.id, sent.message_id, ticket_id, "card")


# -- the queue ------------------------------------------------------------------------


def _waiting_for(updated_at: int, now: int) -> str:
    minutes = max(0, (now - int(updated_at)) // 60)
    if minutes < 60:
        return f"{minutes} мин"
    if minutes < 60 * 24:
        return f"{minutes // 60} ч"
    return f"{minutes // (60 * 24)} дн"


def format_queue(rows: list[dict], page: int, total: int, now: int) -> str:
    lines = [f"🆘 <b>Ждут ответа</b> — {total}, страница {page}\n"]
    for row in rows:
        contact = row.get("email") or (f"@{row['telegram_tag']}" if row.get("telegram_tag") else "") or "—"
        lines.append(
            f"<b>#{row['id']}</b> · {escape(row['subject'])}\n"
            f"  {escape(contact)} · ждёт {_waiting_for(row['updated_at'], now)}"
        )
    lines.append("\nНажмите на обращение, чтобы получить карточку и ответить на неё.")
    return "\n".join(lines)


def queue_label(row: dict) -> str:
    subject = str(row["subject"])
    return f"#{row['id']} · {subject[:40] + '…' if len(subject) > 40 else subject}"


async def render_queue(target: Message, page: int, size: int, edit: bool) -> None:
    total = await _support.count_waiting()
    if not total:
        await target.answer(
            "✅ Все обращения отвечены.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[MENU_BUTTON]]),
        )
        return
    rows = await _support.waiting_page(size, (max(1, page) - 1) * size)
    text = format_queue(rows, page, total, int(time.time()))
    keyboard = picker_keyboard(
        rows,
        label=queue_label,
        item_callback=lambda row: f"support:open:{row['id']}",
        prefix=LIST_PREFIX,
        page=page,
        total=total,
        size=size,
        goto_callback_data=LIST_GOTO,
    )
    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


VIEW = register_view(
    PagedView(name="support", size=PAGE_SIZE, render=render_queue, count=_support.count_waiting)
)


async def _show_queue(target: Message) -> None:
    if not settings.support_enabled:
        await target.answer("Поддержка с сайта выключена (SUPPORT_ENABLED=false).")
        return
    await render_queue(target, 1, PAGE_SIZE, edit=False)


@router.message(Command("tickets"))
async def cmd_tickets(message: Message) -> None:
    await _show_queue(message)


@router.callback_query(F.data == "admin:support")
async def support_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await _show_queue(callback.message)


@router.callback_query(F.data == LIST_GOTO)
async def queue_goto(callback: CallbackQuery, state: FSMContext) -> None:
    await prompt_page_input(callback.message, state, view=VIEW)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{LIST_PREFIX}:"))
async def queue_page(callback: CallbackQuery) -> None:
    try:
        await render_queue(callback.message, parse_page(callback.data), PAGE_SIZE, edit=True)
    except TelegramBadRequest:
        # "message is not modified": the same page pressed twice.
        pass
    await callback.answer()

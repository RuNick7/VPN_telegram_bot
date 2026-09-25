"""
Support tickets as the operators see them in Telegram.

The website stores a ticket; this decides how it reads in a chat -- who is
asking, whether they are paying, what they said -- and how it is sent in a
shape Telegram accepts: text cut under its length limit, files sent as what
they are, and a document in place of a photo Telegram will not take as one.

Everything the customer wrote is escaped before it goes anywhere near HTML.
The admin bot parses every message as HTML by default, so an unescaped `<`
in a subject would at best break the card and at worst format it.
"""

from __future__ import annotations

import html
import logging
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
)
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)

logger = logging.getLogger(__name__)

MOSCOW = ZoneInfo("Europe/Moscow")

# Telegram's limits are 4096 characters for a message and 1024 for a caption,
# counted in UTF-16 units after entities are parsed. The card's header takes
# a few hundred, so the first slice of a customer's text is smaller.
FIRST_PART_LIMIT = 3000
NEXT_PART_LIMIT = 3900

# How long a bot upload may take: a 45 MB recording is not sent in the
# default minute on every connection.
UPLOAD_TIMEOUT = 300

STATUS_LABELS = {
    "open": "ждёт ответа",
    "answered": "отвечено, ждём клиента",
    "closed": "закрыто",
}


def escape(value) -> str:
    return html.escape(str(value if value is not None else ""))


# -- text -------------------------------------------------------------------


def utf16_len(text: str) -> int:
    """Length as Telegram counts it: characters outside the BMP take two."""
    return len(text.encode("utf-16-le")) // 2


def _prefix_within(text: str, limit: int) -> int:
    """How many characters of `text` fit in `limit` UTF-16 units."""
    units = 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > limit:
            return index
    return len(text)


def split_text(text: str, first_limit: int = FIRST_PART_LIMIT, next_limit: int = NEXT_PART_LIMIT) -> list[str]:
    """
    Cut text into pieces Telegram will accept, preferring line breaks, then
    spaces, and a hard cut only when a single word will not fit.
    """
    chunks: list[str] = []
    limit = first_limit
    while utf16_len(text) > limit:
        cut = _prefix_within(text, limit)
        for separator in ("\n", " "):
            boundary = text.rfind(separator, 0, cut)
            if boundary >= cut // 2:
                cut = boundary
                break
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
        limit = next_limit
    chunks.append(text)
    return [chunk for chunk in chunks if chunk] or [""]


def format_size(size: int | None) -> str:
    value = int(size or 0)
    if value < 1024 * 1024:
        return f"{max(1, round(value / 1024))} КБ"
    megabytes = value / (1024 * 1024)
    return f"{megabytes:.0f} МБ" if megabytes >= 10 else f"{megabytes:.1f} МБ".replace(".", ",")


def format_stamp(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts), MOSCOW).strftime("%d.%m %H:%M")


def who(row: dict) -> str:
    """Every handle the customer has, so the operator can find them anywhere."""
    parts = []
    if row.get("email"):
        parts.append(escape(row["email"]))
    if row.get("telegram_tag"):
        parts.append("@" + escape(row["telegram_tag"]))
    if row.get("telegram_id"):
        parts.append(f"tg <code>{int(row['telegram_id'])}</code>")
    return " · ".join(parts) or "без контактов"


def subscription_line(subscription_ends: int | None, now: int) -> str:
    if subscription_ends and subscription_ends > now:
        days = math.ceil((subscription_ends - now) / 86400)
        until = datetime.fromtimestamp(subscription_ends, MOSCOW).strftime("%d.%m.%Y")
        return f"до {until}, осталось {days} дн."
    return "нет активной подписки"


def card_messages(row: dict, now: int) -> list[str]:
    """
    A ticket's opening message: who is asking and what they said.

    The hint at the end is the whole user manual -- an operator who has never
    seen one of these needs to know that a reply is how to answer.
    """
    ticket_id = int(row["ticket_id"])
    parts = split_text(row.get("body") or "")
    files = len(row.get("attachments") or [])
    header = [
        f"🆘 <b>Обращение #{ticket_id}</b>",
        f"<b>{escape(row.get('subject'))}</b>",
        "",
        f"👤 {who(row)}",
        f"💳 Подписка: {subscription_line(row.get('subscription_ends'), now)}",
        f"🆔 <code>{escape(row.get('user_id'))}</code>",
    ]
    if files:
        header.append(f"📎 Файлов: {files} — ниже")
    first = "\n".join(header) + "\n\n" + (escape(parts[0]) or "<i>(без текста)</i>")
    messages = [first] + [f"<i>… продолжение #{ticket_id}</i>\n\n{escape(part)}" for part in parts[1:]]
    messages[-1] += "\n\n<i>↩️ Ответьте на это сообщение, чтобы написать клиенту.</i>"
    return messages


def follow_up_messages(row: dict) -> list[str]:
    """A later message in a ticket. Replies to the card, so it names its ticket briefly."""
    ticket_id = int(row["ticket_id"])
    parts = split_text(row.get("body") or "")
    first = (
        f"💬 <b>#{ticket_id}</b> · {escape(row.get('subject'))}\n"
        f"Новое сообщение клиента:\n\n"
        + (escape(parts[0]) or "<i>(без текста, только файлы)</i>")
    )
    return [first] + [f"<i>… продолжение #{ticket_id}</i>\n\n{escape(part)}" for part in parts[1:]]


def fresh_card(ticket: dict, latest: dict | None, now: int) -> str:
    """A card sent again from the list, showing what the customer said last."""
    body = (latest or {}).get("body") or ""
    parts = split_text(body)
    text = "\n".join(
        [
            f"🆘 <b>Обращение #{int(ticket['id'])}</b> · {STATUS_LABELS.get(ticket['status'], ticket['status'])}",
            f"<b>{escape(ticket.get('subject'))}</b>",
            "",
            f"👤 {who(ticket)}",
            f"💳 Подписка: {subscription_line(ticket.get('subscription_ends'), now)}",
            "",
            "Последнее сообщение клиента"
            + (f" ({format_stamp(latest['created_at'])})" if latest else "")
            + ":",
            escape(parts[0]) or "<i>(без текста)</i>",
        ]
    )
    if len(parts) > 1:
        text += "\n<i>… текст длиннее — полностью в «Вся переписка».</i>"
    files = len((latest or {}).get("attachments") or [])
    if files:
        text += f"\n📎 Файлов в сообщении: {files} — в «Вся переписка»."
    return text + "\n\n<i>↩️ Ответьте на это сообщение, чтобы написать клиенту.</i>"


def history_messages(ticket: dict, thread: list[dict]) -> list[str]:
    """The whole conversation, packed into as few messages as fit."""
    entries = [
        f"📜 <b>Обращение #{int(ticket['id'])}</b> · {escape(ticket.get('subject'))}\n"
        f"Статус: {STATUS_LABELS.get(ticket['status'], ticket['status'])} · сообщений: {len(thread)}"
    ]
    for message in thread:
        author = "👤 Клиент" if message["author"] == "user" else "🛟 Поддержка"
        lines = [f"— <b>{author}</b> · {format_stamp(message['created_at'])}"]
        for part in split_text(message.get("body") or "", NEXT_PART_LIMIT - 200, NEXT_PART_LIMIT - 200):
            if part:
                lines.append(escape(part))
        for attachment in message.get("attachments") or []:
            state = " — удалён по сроку" if attachment.get("purged") else ""
            lines.append(f"📎 {escape(attachment['file_name'])} ({format_size(attachment['size_bytes'])}){state}")
        entries.append("\n".join(lines))

    messages: list[str] = []
    current = ""
    for entry in entries:
        candidate = f"{current}\n\n{entry}" if current else entry
        if current and utf16_len(candidate) > NEXT_PART_LIMIT:
            messages.append(current)
            current = entry
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def customer_notice(ticket_id: int, subject: str, replies: list[dict], *, with_link: bool) -> str:
    """What the customer is told in user_bot when an operator has answered."""
    text = "\n\n".join(r["body"].strip() for r in replies if (r.get("body") or "").strip())
    if utf16_len(text) > FIRST_PART_LIMIT:
        text = text[: _prefix_within(text, FIRST_PART_LIMIT - 1)].rstrip() + "…"
    files = sum(int(r.get("attachment_count") or 0) for r in replies)

    lines = [f"💬 <b>Ответ поддержки</b> · обращение #{int(ticket_id)}", f"«{escape(subject)}»", ""]
    if text:
        lines += [escape(text), ""]
    if files:
        lines.append(f"📎 Файлов в ответе: {files} — они в личном кабинете.")
    lines.append(
        "Продолжить переписку можно в личном кабинете."
        if with_link
        else "Продолжить переписку можно в личном кабинете на сайте."
    )
    return "\n".join(lines)


def clean_name(name: str | None, fallback: str) -> str:
    """A file name from Telegram, without a path and within a sensible length."""
    base = os.path.basename((name or "").replace("\\", "/")).strip() or fallback
    base = "".join(char for char in base if char.isprintable())
    if len(base) > 100:
        stem, ext = os.path.splitext(base)
        base = stem[: 100 - len(ext)] + ext
    return base or fallback


# -- buttons ------------------------------------------------------------------


def ticket_keyboard(ticket_id: int, *, closed: bool = False) -> InlineKeyboardMarkup:
    toggle = (
        InlineKeyboardButton(text="♻️ Открыть снова", callback_data=f"support:reopen:{ticket_id}")
        if closed
        else InlineKeyboardButton(text="✅ Закрыть", callback_data=f"support:close:{ticket_id}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle, InlineKeyboardButton(text="👤 Клиент", callback_data=f"support:client:{ticket_id}")],
            [InlineKeyboardButton(text="📜 Вся переписка", callback_data=f"support:history:{ticket_id}")],
        ]
    )


# -- sending ------------------------------------------------------------------


def chat_unreachable(exc: BaseException) -> bool:
    """
    This chat cannot receive anything: the bot was blocked, or never started,
    or the id is not a chat at all. Retrying will not change that, and one
    such chat must not hold up delivery to everybody else.
    """
    if isinstance(exc, TelegramForbiddenError):
        return True
    return isinstance(exc, TelegramBadRequest) and "chat not found" in str(exc).lower()


def refused(exc: BaseException) -> bool:
    """
    Telegram refuses this particular message and would refuse it again.

    TelegramEntityTooLarge is checked by name because it derives from
    TelegramNetworkError -- read as a network blip, an oversized file would be
    retried forever and block every ticket queued behind it.
    """
    if isinstance(exc, TelegramEntityTooLarge):
        return True
    return isinstance(exc, TelegramBadRequest) and not chat_unreachable(exc)


def reply_to(message_id: int | None) -> ReplyParameters | None:
    """Thread onto a message if it still exists; send standalone if it was deleted."""
    if not message_id:
        return None
    return ReplyParameters(message_id=int(message_id), allow_sending_without_reply=True)


async def send_file(
    bot: Bot,
    chat_id: int,
    *,
    name: str,
    content_type: str,
    data: bytes,
    caption: str,
    reply_to_id: int | None,
) -> Message:
    """
    Send a file the way Telegram shows it best: a photo as a photo, an MP4 as
    a video, anything else as a document.

    A photo Telegram will not take as one -- a long screenshot past its
    dimension limits, most often -- still goes, as a document. Only the chat
    being unreachable, or the document itself being refused, reaches the
    caller.
    """
    reply = reply_to(reply_to_id)
    try:
        if content_type in ("image/jpeg", "image/png") and len(data) <= 10 * 1024 * 1024:
            return await bot.send_photo(
                chat_id, BufferedInputFile(data, filename=name),
                caption=caption, reply_parameters=reply, request_timeout=UPLOAD_TIMEOUT,
            )
        if content_type == "video/mp4":
            return await bot.send_video(
                chat_id, BufferedInputFile(data, filename=name),
                caption=caption, supports_streaming=True,
                reply_parameters=reply, request_timeout=UPLOAD_TIMEOUT,
            )
    except TelegramBadRequest as exc:
        if chat_unreachable(exc):
            raise
        logger.info("Telegram would not take %s as media (%s); sending it as a document", name, exc)
    return await bot.send_document(
        chat_id, BufferedInputFile(data, filename=name),
        caption=caption, reply_parameters=reply, request_timeout=UPLOAD_TIMEOUT,
    )

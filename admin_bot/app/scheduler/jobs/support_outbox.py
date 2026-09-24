"""
Carries support tickets between the website and Telegram.

The website only writes rows -- it holds no bot token, being the most exposed
process in the deployment -- so everything a ticket needs sent is sent from
here. Every few seconds this reads what is waiting and delivers it:

* a customer's message goes to every ADMIN_IDS chat: a card for a new
  ticket, a reply to that card for a later message, each file as a reply to
  its text;
* a ticket the customer closed is announced there, so nobody answers one that
  is finished;
* an operator's answer is announced to the customer through user_bot -- the
  bot they actually talk to -- when they have a Telegram to announce it in.

Delivery is resumable. Every Telegram message is recorded against what it
carries before the next one is sent, so a pass that dies halfway through a
message's files resends only what did not arrive. Messages go strictly
oldest first, and a pass stops at the first failure that might be temporary,
so a follow-up never lands before the card it replies to.

A failure that is not temporary never blocks the queue. A chat that cannot
receive (the bot blocked, or never started) is skipped; a file Telegram
refuses is replaced by a line saying so. Either way the operators still get
everything else.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from html import unescape

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from tgvpn_shared.db import JobRunRepository, SupportRepository

from app.config.settings import settings
from app.services.support import (
    card_messages,
    chat_unreachable,
    customer_notice,
    escape,
    follow_up_messages,
    format_size,
    refused,
    reply_to,
    send_file,
    ticket_keyboard,
)

logger = logging.getLogger(__name__)

JOB_NAME = "support_outbox"

# Short enough that a ticket reaches an operator while the customer is still
# looking at the page they sent it from. The query behind it reads a partial
# index that is empty almost all the time.
POLL_SECONDS = 5

# A success recorded every five seconds would be a database write every five
# seconds for nobody: the health monitor judges staleness in minutes.
RECORD_SUCCESS_EVERY = 60

_support = SupportRepository()
_jobs = JobRunRepository()

_NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


async def run_support_outbox(bot: Bot) -> None:
    """
    Forever: one pass, a pause, again. Never raises, except to be cancelled.

    A loop of its own rather than a scheduler job: passes must not overlap
    (two of them would deliver the same message twice), and a pass carrying a
    45 MB video can outlast any interval short enough to be useful.
    """
    last_recorded = 0.0
    while True:
        delay = POLL_SECONDS
        started = time.monotonic()
        try:
            await run_pass(bot)
        except asyncio.CancelledError:
            raise
        except TelegramRetryAfter as exc:
            delay = max(POLL_SECONDS, int(exc.retry_after))
            last_recorded = 0.0
            await _record(failure=f"Telegram просит подождать {exc.retry_after} с")
        except Exception as exc:
            logger.warning("Support outbox pass failed: %s", exc, exc_info=True)
            last_recorded = 0.0
            await _record(failure=str(exc))
        else:
            if time.monotonic() - last_recorded >= RECORD_SUCCESS_EVERY:
                await _record(duration_ms=int((time.monotonic() - started) * 1000))
                last_recorded = time.monotonic()
        await asyncio.sleep(delay)


async def _record(*, failure: str | None = None, duration_ms: int | None = None) -> None:
    # The bookkeeping must not be what kills the loop -- a database that is
    # down fails the pass anyway, and the next pass will say so again.
    try:
        if failure is None:
            await _jobs.record_success(JOB_NAME, duration_ms)
        else:
            await _jobs.record_failure(JOB_NAME, failure)
    except Exception as exc:
        logger.warning("Could not record support outbox run: %s", exc)


async def run_pass(bot: Bot) -> None:
    """Deliver everything waiting, oldest first. Raises on a temporary failure."""
    chats = settings.admin_ids
    if chats:
        now = int(time.time())
        for message in await _support.pending_customer_messages():
            await deliver_to_operators(bot, message, chats, now)
        for ticket in await _support.pending_close_announcements():
            await announce_close(bot, ticket, chats)
    else:
        logger.warning("ADMIN_IDS is empty; support tickets have nowhere to go")
    await notify_customers()


# -- customer -> operators --------------------------------------------------------


async def deliver_to_operators(bot: Bot, message: dict, chats: list[int], now: int) -> None:
    sent = await _support.delivered_parts(message["id"])
    for chat_id in chats:
        try:
            await _deliver_to_chat(bot, chat_id, message, sent, now)
        except Exception as exc:
            if chat_unreachable(exc):
                logger.warning("Support: chat %s cannot receive (%s); skipped", chat_id, exc)
                continue
            await _support.record_delivery_failure(message["id"], str(exc))
            raise
    await _support.mark_delivered(message["id"])


async def _deliver_to_chat(bot: Bot, chat_id: int, message: dict, sent: dict, now: int) -> None:
    text_id = sent.get((chat_id, None))
    if text_id is None:
        text_id = await _send_text(bot, chat_id, message, now)
    for attachment in message["attachments"]:
        if (chat_id, attachment["id"]) not in sent:
            await _send_attachment(bot, chat_id, message, attachment, text_id)


async def _send_text(bot: Bot, chat_id: int, message: dict, now: int) -> int:
    """Send a message's text, in as many parts as it takes. Returns the first."""
    ticket_id = int(message["ticket_id"])
    if message["opens_ticket"]:
        parts, kind, reply = card_messages(message, now), "card", None
    else:
        parts, kind = follow_up_messages(message), "text"
        reply = await _support.card_for(ticket_id, chat_id)

    # Every part is sent before any is recorded. A record is what tells the
    # next pass "the text is done", so recording the first part of two and
    # then failing would leave the second unsent for good. Recording none
    # until all are out means the worst a failure costs is a repeated part.
    sent_ids: list[int] = []
    for index, text in enumerate(parts):
        sent = await _send_html(
            bot, chat_id, text,
            reply_to_id=reply if index == 0 else sent_ids[0],
            keyboard=ticket_keyboard(ticket_id) if index == len(parts) - 1 else None,
        )
        sent_ids.append(sent.message_id)
    for index, telegram_message_id in enumerate(sent_ids):
        await _support.record_telegram_message(
            chat_id, telegram_message_id, ticket_id, kind if index == 0 else "text",
            support_message_id=message["id"],
        )
    return sent_ids[0]


async def _send_html(bot: Bot, chat_id: int, text: str, *, reply_to_id=None, keyboard=None):
    """
    Send HTML, falling back to the same words as plain text.

    Everything interpolated is escaped, so the fallback should never run. It
    is here because the alternative, if it ever did, is a message Telegram
    refuses on every pass and every ticket behind it stuck.
    """
    try:
        return await bot.send_message(
            chat_id, text, reply_parameters=reply_to(reply_to_id),
            reply_markup=keyboard, link_preview_options=_NO_PREVIEW,
        )
    except Exception as exc:
        if not refused(exc):
            raise
        logger.error("Telegram refused a support message as HTML (%s); sending it as plain text", exc)
        return await bot.send_message(
            chat_id, unescape(re.sub(r"<[^>]+>", "", text)), parse_mode=None,
            reply_parameters=reply_to(reply_to_id), reply_markup=keyboard,
            link_preview_options=_NO_PREVIEW,
        )


async def _send_attachment(bot: Bot, chat_id: int, message: dict, attachment: dict, text_id: int) -> None:
    ticket_id = int(message["ticket_id"])
    name = attachment["file_name"]
    caption = f"📎 #{ticket_id} · {escape(name)} · {format_size(attachment['size_bytes'])}"

    data = None if attachment["purged"] else await _support.attachment_data(attachment["id"])
    if data is None:
        sent = await _send_html(
            bot, chat_id, f"📎 #{ticket_id} · {escape(name)} — файл уже удалён по сроку хранения.",
            reply_to_id=text_id,
        )
        kind = "notice"
    else:
        try:
            sent = await send_file(
                bot, chat_id, name=name, content_type=attachment["content_type"],
                data=data, caption=caption, reply_to_id=text_id,
            )
            kind = "attachment"
        except Exception as exc:
            if not refused(exc):
                raise
            # Asking again will not change Telegram's mind. Saying so in the
            # file's place keeps everything queued behind it moving.
            logger.warning("Telegram refused support file %s: %s", attachment["id"], exc)
            sent = await _send_html(
                bot, chat_id,
                f"⚠️ #{ticket_id}: Telegram не принял файл «{escape(name)}» "
                f"({format_size(attachment['size_bytes'])}): {escape(str(exc))[:200]}. "
                f"Попросите клиента прислать его иначе.",
                reply_to_id=text_id,
            )
            kind = "notice"
    await _support.record_telegram_message(
        chat_id, sent.message_id, ticket_id, kind,
        support_message_id=message["id"], attachment_id=attachment["id"],
    )


async def announce_close(bot: Bot, ticket: dict, chats: list[int]) -> None:
    ticket_id = int(ticket["id"])
    for chat_id in chats:
        card = await _support.card_for(ticket_id, chat_id)
        try:
            sent = await _send_html(
                bot, chat_id,
                f"🔒 Клиент закрыл обращение <b>#{ticket_id}</b> · {escape(ticket['subject'])}",
                reply_to_id=card,
            )
        except Exception as exc:
            if chat_unreachable(exc):
                continue
            raise
        await _support.record_telegram_message(chat_id, sent.message_id, ticket_id, "notice")
    await _support.mark_close_announced(ticket_id)


# -- operators -> customer --------------------------------------------------------


def _ticket_url(ticket_id: int) -> str:
    base = settings.web_base_url.strip().rstrip("/")
    # Telegram accepts only http(s) in a URL button, and a site on localhost
    # is not one a customer's phone can open anyway.
    if not base.startswith("https://"):
        return ""
    return f"{base}/app/support?id={ticket_id}"


async def notify_customers() -> None:
    """
    Tell customers an answer is waiting, once per ticket per pass.

    An operator who answers in three messages -- or sends an album, which
    arrives as one message per picture -- produces one notification, not
    three.
    """
    pending = await _support.pending_operator_replies()
    by_ticket: dict[int, list[dict]] = {}
    for reply in pending:
        by_ticket.setdefault(int(reply["ticket_id"]), []).append(reply)

    for ticket_id, replies in by_ticket.items():
        ids = [int(reply["id"]) for reply in replies]
        telegram_id = replies[0]["telegram_id"]
        if not telegram_id or not settings.user_bot_token:
            # Nothing to tell them in. The answer is in their cabinet, and the
            # dot on the support tab says so.
            await _support.mark_delivered(*ids)
            continue
        try:
            await _notify_customer(int(telegram_id), ticket_id, replies)
        except Exception as exc:
            if chat_unreachable(exc) or refused(exc):
                logger.info("Support: could not tell %s about #%s (%s)", telegram_id, ticket_id, exc)
                await _support.mark_delivered(*ids)
                continue
            for reply_id in ids:
                await _support.record_delivery_failure(reply_id, str(exc))
            raise
        await _support.mark_delivered(*ids)


async def _notify_customer(telegram_id: int, ticket_id: int, replies: list[dict]) -> None:
    """
    From user_bot, which is the bot the customer talks to. A fresh Bot per
    send, as the traffic monitor does it: this is rare, and a session held by
    the loop would outlive it on shutdown.
    """
    url = _ticket_url(ticket_id)
    keyboard = (
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть обращение", url=url)]])
        if url
        else None
    )
    bot = Bot(token=settings.user_bot_token.strip())
    try:
        await bot.send_message(
            telegram_id,
            customer_notice(ticket_id, replies[0]["subject"], replies, with_link=bool(url)),
            parse_mode="HTML",
            reply_markup=keyboard,
            link_preview_options=_NO_PREVIEW,
        )
    finally:
        await bot.session.close()

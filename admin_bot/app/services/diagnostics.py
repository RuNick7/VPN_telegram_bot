"""
Asking a customer for a server-check report.

The question goes out through user_bot, the bot the customer talks to, with
the list of what would be collected; the answer is handled there
(user_bot/handlers/support_diag.py). Nothing is collected unless they say yes,
and even then the vpncheck program asks again before sending anything.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Message
from tgvpn_shared.support_diagnostics import CALLBACK_ALLOW, CALLBACK_DENY, consent_text

from app.config.settings import settings
from app.services.support import escape


def consent_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Согласен", callback_data=f"{CALLBACK_ALLOW}{request_id}"),
            InlineKeyboardButton(text="❌ Не согласен", callback_data=f"{CALLBACK_DENY}{request_id}"),
        ]]
    )


async def ask_customer(telegram_id: int, request_id: int, ticket_id: int, subject: str) -> Message:
    """
    Send the question from user_bot. A fresh Bot per send, as the support
    outbox does it: this is rare, and a held session would outlive its loop.
    """
    bot = Bot(token=settings.user_bot_token.strip())
    try:
        return await bot.send_message(
            telegram_id,
            consent_text(ticket_id, subject),
            parse_mode="HTML",
            reply_markup=consent_keyboard(request_id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    finally:
        await bot.session.close()


def decision_notice(request: dict) -> str:
    """What the operators are told once the customer has answered."""
    ticket = f"<b>#{int(request['ticket_id'])}</b> · {escape(request['subject'])}"
    if request["decision"] == "granted":
        return (
            f"🩺 Клиент согласился на проверку серверов по {ticket}. "
            f"Отчёт придёт сюда файлом, когда клиент запустит программу и подтвердит отправку."
        )
    return f"🩺 Клиент отказался от проверки серверов по {ticket}."

"""
Attaching a confirmed email address to a Telegram account.

The mirror of `account_link.py`. That module attaches Telegram to an account
that arrived by email; this one attaches an address to an account that arrived
through the bot. Both pay the same bonus, for the same reason: an account with
one identity can be locked out of it -- a Telegram ban, a lost number -- and
the second one is what makes the subscription recoverable.

**The address is never taken on trust.** The bot used to save whatever was
typed, immediately, and that address is a sign-in route on the website: a
typo silently handed someone else's mailbox the ability to request a login
link for this account. Now nothing is written until a letter sent to the
address has been opened, which is the same standard the site holds itself to.

The offer is made once. `bonus_offer_shown_in_bot` records that it has been,
so the bot does not turn into a thing that asks for your email every time you
open it.
"""

from __future__ import annotations

import logging
import re
import secrets

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.db import EmailVerificationRepository, UserRepository
from tgvpn_shared.mailer import MailNotConfigured, MailSendFailed, send_email_confirmation
from tgvpn_shared.settings import get_settings

from handlers.constants import trial_link_bonus_days

logger = logging.getLogger(__name__)

_users = UserRepository()
_verifications = EmailVerificationRepository()

# Short, because the whole flow is "type it, open the letter". Anything left
# lying around afterwards is a token that binds a sign-in route to an account.
CONFIRM_TTL_SECONDS = 30 * 60

# Deliberately loose. Anything stricter rejects real addresses, and the actual
# test of an address is whether the letter arrives -- which is the next step.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def looks_like_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def offer_keyboard() -> InlineKeyboardMarkup:
    bonus = trial_link_bonus_days()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📧 Привязать почту (+{bonus} дн.)", callback_data="change_email")],
            [InlineKeyboardButton(text="Не сейчас", callback_data="bonus_offer_dismiss")],
        ]
    )


def offer_text() -> str:
    bonus = trial_link_bonus_days()
    return (
        "📧 <b>Добавьте почту — получите "
        f"{bonus} дн. подписки</b>\n\n"
        "Почта нужна, чтобы вход в личный кабинет на сайте работал, "
        "даже если Telegram окажется недоступен.\n\n"
        "Мы пришлём письмо со ссылкой для подтверждения. "
        "Дни начислятся сразу после перехода по ней."
    )


async def should_offer(row) -> bool:
    """
    Whether this account has anything to gain from the offer.

    Four ways to answer no, and each is its own reason: the bonus is switched
    off, mail cannot be sent at all, the address is already there, or we have
    already asked. The last two are what keep it a one-time offer rather than
    a recurring interruption.
    """
    if trial_link_bonus_days() <= 0 or not get_settings().mail_configured:
        return False
    if row is None or row["email"]:
        return False
    if row["trial_link_granted"]:
        return False
    return not (row["bonus_offer_shown_in_bot"] or row["bonus_offer_dismissed"])


async def send_confirmation(user_id: str, email: str) -> str:
    """
    Issue a token and post the letter. Returns a message for the customer.

    The token is minted before the send and dropped if the send fails, so a
    provider outage does not leave a live token for an address nobody proved.
    """
    settings = get_settings()
    base = settings.web_base_url.strip().rstrip("/")
    if not base:
        logger.error("[EMAIL] WEB_BASE_URL is unset; the confirmation link would go nowhere")
        return "❌ Подтверждение почты сейчас недоступно. Напишите в поддержку."

    token = secrets.token_urlsafe(32)
    await _verifications.create(token, user_id, email, CONFIRM_TTL_SECONDS)
    link = f"{base}/auth/confirm-email?token={token}"

    try:
        await send_email_confirmation(
            email, link, trial_link_bonus_days(), CONFIRM_TTL_SECONDS // 60
        )
    except MailNotConfigured:
        logger.error("[EMAIL] Asked to confirm %s with no SMTP configured", email)
        return "❌ Отправка почты не настроена. Напишите в поддержку."
    except MailSendFailed as exc:
        logger.error("[EMAIL] Could not send confirmation to %s: %s", email, exc)
        return (
            "❌ Не удалось отправить письмо. Проверьте адрес и попробуйте ещё раз "
            "или напишите в поддержку."
        )

    logger.info("[EMAIL] Confirmation sent for user %s", user_id)
    return (
        f"📨 <b>Письмо отправлено на {email}</b>\n\n"
        f"Откройте ссылку из письма — она действует {CONFIRM_TTL_SECONDS // 60} мин.\n"
        f"После подтверждения начислим <b>{trial_link_bonus_days()} дн.</b>\n\n"
        "Письма нет? Проверьте папку «Спам»."
    )

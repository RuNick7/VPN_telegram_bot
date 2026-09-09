"""
Outgoing mail for the bots.

The website has its own sender in Go (`web/internal/mailer`) and keeps it --
the two processes do not share a runtime, and routing the bot's mail through
the site would mean an internal API and a secret to guard it, for one message.
What they do share is the SMTP account: both read the same `SMTP_*` keys out of
the same `.env`, so there is one mailbox to configure and one place a wrong
password shows up.

One rule is copied from the Go side deliberately: **there is no mock sender**.
The backend this project replaced had exactly one implemented mode, a mock that
printed to stdout, and it returned the confirmation token in the API response
whenever that mock was active -- so "email verification" verified nothing.
A sender that cannot reach a real mailbox raises.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from .settings import get_settings

logger = logging.getLogger(__name__)

# Ceiling on the whole SMTP conversation. Without one a provider that accepts
# the connection and then stops talking holds an aiogram worker forever.
SMTP_TIMEOUT_SECONDS = 20


class MailNotConfigured(Exception):
    """No SMTP account is set up, so nothing can be sent."""


class MailSendFailed(Exception):
    """The provider refused the message or could not be reached."""


def _build(to: str, subject: str, body: str, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


def _send_blocking(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.mail_configured:
        raise MailNotConfigured("SMTP_HOST and SMTP_FROM are required to send mail")

    sender = settings.smtp_from.strip()
    message = _build(to, subject, body, sender)
    context = ssl.create_default_context()

    try:
        if settings.smtp_starttls:
            with smtplib.SMTP(
                settings.smtp_host.strip(), settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
            ) as client:
                client.starttls(context=context)
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
        else:
            # Implicit TLS, which is what port 465 speaks.
            with smtplib.SMTP_SSL(
                settings.smtp_host.strip(),
                settings.smtp_port,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=context,
            ) as client:
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        # The password length, never the password: a truncated paste is the
        # usual cause and this is what makes it visible.
        raise MailSendFailed(
            f"SMTP rejected the credentials for {settings.smtp_username!r} "
            f"(password length {len(settings.smtp_password)}): {exc}"
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise MailSendFailed(f"could not send via {settings.smtp_host}: {exc}") from exc


async def send_mail(to: str, subject: str, body: str) -> None:
    """
    Send one message, off the event loop.

    smtplib is blocking and a slow provider would otherwise stall every other
    update the bot is handling.
    """
    await asyncio.to_thread(_send_blocking, to, subject, body)


async def send_email_confirmation(to: str, link: str, bonus_days: int, ttl_minutes: int) -> None:
    """The letter that attaches an address to a Telegram account."""
    body = (
        "Здравствуйте!\n\n"
        "Вы указали этот адрес в боте KairaVPN. Чтобы привязать его к аккаунту "
        f"и получить {bonus_days} дн. подписки, откройте ссылку:\n\n{link}\n\n"
        f"Ссылка действует {ttl_minutes} мин. и срабатывает один раз.\n\n"
        "Если вы этого не делали — просто проигнорируйте письмо. Ничего "
        "с вашим адресом не произошло, и он ни к чему не привязан.\n"
    )
    await send_mail(to, "Подтверждение почты — KairaVPN", body)

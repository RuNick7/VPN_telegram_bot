"""
Server-check reports in support tickets, and the customer's consent to them.

An operator asks from a ticket card in admin_bot. The customer is asked in
user_bot -- the bot they talk to -- with the list of what would be collected,
and answers yes or no there. A yes gives them a one-time code; the vpncheck
program takes the code, checks the servers from their computer, shows them
the report, and attaches it to the ticket once they agree a second time.

Both bots need the same words and the same code rules, so they live here.
The website hashes codes the same way (`web/internal/support/diagnostics.go`);
the vectors in the tests on both sides keep the two from drifting.
"""

from __future__ import annotations

import hashlib
import html
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

# No 0/O or 1/I: the code is read off a phone and typed on a computer.
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LENGTH = 12  # 60 bits, rate-limited by the site, alive for days at most

# How long a code works once given.
CODE_TTL_SECONDS = 72 * 3600
# How long a question waits for an answer before it no longer counts.
REQUEST_TTL_SECONDS = 7 * 86400

CALLBACK_ALLOW = "diag:allow:"
CALLBACK_DENY = "diag:deny:"

_MOSCOW = ZoneInfo("Europe/Moscow")


def generate_code() -> str:
    """A fresh code, as shown: XXXX-XXXX-XXXX."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize_code(text: str) -> str | None:
    """A code as typed -- any case, dashes or spaces -- or None if it is not one."""
    raw = "".join(ch for ch in (text or "").upper() if ch not in "- ")
    if len(raw) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in raw):
        return None
    return raw


def hash_code(code: str) -> bytes:
    """What the database keeps instead of the code."""
    raw = normalize_code(code)
    if raw is None:
        raise ValueError("not a diagnostics code")
    return hashlib.sha256(raw.encode("ascii")).digest()


# -- what the customer reads ----------------------------------------------------

# Said in full before anything is agreed to: a customer cannot consent to
# what they were not told.
COLLECTED = (
    "• к каким серверам из вашей подписки удалось подключиться, а к каким нет, и на каком шаге;\n"
    "• время ответа серверов и скорость (если включить замер);\n"
    "• технический журнал подключения (лог Xray) по каждому серверу;\n"
    "• страну, из которой идёт проверка, и тип системы (Windows, macOS, Linux)."
)

NOT_COLLECTED = (
    "Ключи, пароли, идентификаторы и ссылка на подписку вырезаются из отчёта до отправки, "
    "ваш IP-адрес в него не попадает. Перед отправкой программа покажет готовый файл "
    "и спросит ещё раз."
)


def consent_text(ticket_id: int, subject: str) -> str:
    """The question, as HTML."""
    return (
        f"🩺 <b>Поддержка просит отчёт о проверке серверов</b>\n"
        f"Обращение #{int(ticket_id)} «{html.escape(subject or '')}»\n\n"
        f"Это поможет понять, почему не работает VPN. Если вы согласитесь, вы получите "
        f"код и ссылку на программу vpncheck для компьютера (Windows, macOS или Linux). "
        f"Программа подключится к каждому серверу из вашей подписки так же, как приложение, "
        f"и соберёт:\n{COLLECTED}\n\n"
        f"{NOT_COLLECTED}\n\n"
        f"Поддержка сверит отчёт с журналами наших серверов за время проверки.\n\n"
        f"В списке ваших устройств появится «vpncheck» — после проверки его можно удалить.\n\n"
        f"Без вашего согласия ничего не собирается и не отправляется."
    )


def granted_text(ticket_id: int, subject: str, code: str, download_url: str, expires_at: int) -> str:
    until = datetime.fromtimestamp(int(expires_at), _MOSCOW).strftime("%d.%m %H:%M")
    return (
        f"🩺 <b>Спасибо, вы согласились</b>\n"
        f"Обращение #{int(ticket_id)} «{html.escape(subject or '')}»\n\n"
        f"1. Выключите VPN-приложение.\n"
        f"2. Скачайте программу для своего компьютера: {html.escape(download_url)}\n"
        f"3. Запустите её и введите код:\n\n"
        f"<code>{html.escape(code)}</code>\n\n"
        f"Код действует до {until} (МСК) и подходит один раз. Программа покажет итог, "
        f"сохранит отчёт на компьютере и спросит, отправить ли его в обращение.\n\n"
        f"Никому не пересылайте этот код."
    )


def declined_text(ticket_id: int, subject: str) -> str:
    return (
        f"🩺 Вы отказались от проверки серверов по обращению #{int(ticket_id)} "
        f"«{html.escape(subject or '')}». Ничего не собрано и не отправлено. "
        f"Поддержка продолжит разбираться по переписке."
    )


def stale_text() -> str:
    return "🩺 Этот запрос больше не действует. Если поддержка попросит снова, придёт новый."

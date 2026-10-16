"""
The customer's answer to a support request for a server-check report.

admin_bot sends the question from this bot (it is the one the customer talks
to), listing what would be collected; the two buttons land here. A yes gives
the customer a one-time code for the vpncheck program, which sends the report
into the ticket only after showing it and asking once more. A no is final for
that request, and the operators are told either way.

Only the ticket's owner can answer. The question went to their chat, but a
forwarded message keeps its buttons, and nobody else's tap may agree on their
behalf.
"""

import logging

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from tgvpn_shared.db import SupportDiagnosticsRepository
from tgvpn_shared.settings import get_settings
from tgvpn_shared.support_diagnostics import (
    CALLBACK_ALLOW,
    CALLBACK_DENY,
    CODE_TTL_SECONDS,
    declined_text,
    generate_code,
    granted_text,
    hash_code,
    stale_text,
)

router = Router()
logger = logging.getLogger(__name__)

_diagnostics = SupportDiagnosticsRepository()


def _request_id(data: str | None) -> int:
    tail = (data or "").rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else 0


async def _replace(callback: types.CallbackQuery, text: str) -> None:
    """The answer in place of the question, so its buttons cannot be pressed again."""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=None)
    except (TelegramBadRequest, AttributeError):
        # Too old to edit: say it as a new message instead.
        await callback.message.answer(text, parse_mode="HTML")


async def _load(callback: types.CallbackQuery) -> dict | None:
    """The request if this person may answer it now; otherwise says why and returns None."""
    request = await _diagnostics.get(_request_id(callback.data))
    if request is None or request["telegram_id"] != callback.from_user.id:
        await callback.answer("Этот запрос не для вас.", show_alert=True)
        return None
    if request["decision"] is not None:
        await callback.answer("Вы уже ответили на этот запрос.")
        await _replace_buttons_only(callback)
        return None
    if not request["fresh"] or request["status"] == "closed":
        await callback.answer()
        await _replace(callback, stale_text())
        return None
    return request


async def _replace_buttons_only(callback: types.CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except (TelegramBadRequest, AttributeError):
        pass


@router.callback_query(F.data.startswith(CALLBACK_ALLOW))
async def allow(callback: types.CallbackQuery) -> None:
    request = await _load(callback)
    if request is None:
        return
    download_url = get_settings().vpncheck_download_url.strip()
    if not download_url:
        # Switched off since the question was sent. Leave it unanswered: an
        # operator can ask again once there is something to download.
        await callback.answer("Проверка сейчас недоступна. Поддержка напишет вам в обращении.", show_alert=True)
        return
    code = generate_code()
    expires_at = await _diagnostics.grant(request["id"], hash_code(code), CODE_TTL_SECONDS)
    if expires_at is None:
        # Answered in another tap a moment ago, or just gone stale.
        await callback.answer("Вы уже ответили на этот запрос.")
        await _replace_buttons_only(callback)
        return
    await callback.answer("Спасибо!")
    await _replace(
        callback,
        granted_text(request["ticket_id"], request["subject"], code, download_url, int(expires_at)),
    )
    logger.info("Diagnostics request %s granted for ticket #%s", request["id"], request["ticket_id"])


@router.callback_query(F.data.startswith(CALLBACK_DENY))
async def deny(callback: types.CallbackQuery) -> None:
    request = await _load(callback)
    if request is None:
        return
    if not await _diagnostics.decline(request["id"]):
        await callback.answer("Вы уже ответили на этот запрос.")
        await _replace_buttons_only(callback)
        return
    await callback.answer("Хорошо, ничего не собираем.")
    await _replace(callback, declined_text(request["ticket_id"], request["subject"]))
    logger.info("Diagnostics request %s declined for ticket #%s", request["id"], request["ticket_id"])

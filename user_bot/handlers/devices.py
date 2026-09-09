"""
Self-service for a user's own subscription: rotate the link, drop a device.

Both actions are destructive in ways the user can't undo, so both go through a
confirmation step. Devices are addressed by a hash of their HWID rather than
by position in the list: callback data caps at 64 bytes so the raw HWID will
not fit, and an index would quietly select a *different* device if the list
shifted between rendering the keyboard and the user tapping it. A hash either
matches the device they picked or matches nothing.
"""

import asyncio
import hashlib
import logging
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.remnawave import UserNotFoundError

from app.services.remnawave.vpn_service import (
    delete_device,
    get_client,
    get_devices,
    reset_subscription_url,
)
from handlers.keyboards import back_to_devices_keyboard, pay_keyboard

router = Router()
logger = logging.getLogger(__name__)

# Ceiling on the panel round-trip behind a button, so a slow Remnawave shows a
# retry prompt instead of an unresponsive button. Matches setup.py's.
PANEL_TIMEOUT_SECONDS = 10.0

# How much of a device label fits on a button without wrapping badly.
_LABEL_MAX = 32


def device_token(hwid: str) -> str:
    """A short, stable handle for a device -- callback data caps at 64 bytes."""
    return hashlib.sha256(hwid.encode("utf-8")).hexdigest()[:16]


def device_label(device: dict) -> str:
    """Something a person recognises as their phone, from whatever the panel has."""
    parts = [
        str(device.get(key) or "").strip()
        for key in ("deviceModel", "platform", "osVersion")
    ]
    # dict.fromkeys dedupes while keeping order: some panels report the model
    # and the platform identically, and "iPhone · iPhone" reads like a bug.
    named = " · ".join(dict.fromkeys(part for part in parts if part))
    if named:
        return named
    agent = str(device.get("userAgent") or "").strip()
    return agent[:_LABEL_MAX] if agent else "Неизвестное устройство"


def _truncate(text: str) -> str:
    return text if len(text) <= _LABEL_MAX else text[: _LABEL_MAX - 1] + "…"


def devices_keyboard(devices: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"❌ {_truncate(device_label(device))}",
                callback_data=f"device_del:{device_token(str(device.get('hwid') or ''))}",
            )
        ]
        for device in devices
        if device.get("hwid")
    ]
    rows.append([InlineKeyboardButton(text="🔙 К выбору устройства", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_keyboard(confirm_data: str, *, confirm_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=confirm_text, callback_data=confirm_data)],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="my_devices")],
        ]
    )


async def _panel_call(cb: CallbackQuery, coro):
    """
    Await a panel call, replying to the user on the failures we expect.

    Returns a `(ok, value)` pair rather than raising, so each handler can stop
    quietly after the user has already been told what went wrong.
    """
    try:
        return True, await asyncio.wait_for(coro, timeout=PANEL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await cb.answer("⏱ Сервер не отвечает, попробуйте через минуту.", show_alert=True)
    except UserNotFoundError:
        await cb.answer()
        await cb.message.answer(
            "🚫 Профиль не найден на сервере.\n\nОформите подписку, чтобы получить доступ:",
            parse_mode="HTML",
            reply_markup=pay_keyboard(),
        )
    except Exception as exc:
        # A stale cached token looks exactly like this; drop it so the user's
        # next attempt authenticates freshly.
        get_client().invalidate_token()
        logger.error("[DEVICES] Panel call failed for %s: %s", cb.from_user.id, exc)
        await cb.answer("❌ Не удалось связаться с сервером. Попробуйте позже.", show_alert=True)
    return False, None


# -- device list -----------------------------------------------------------


@router.callback_query(F.data == "my_devices")
async def show_devices(cb: CallbackQuery) -> None:
    ok, result = await _panel_call(cb, get_devices(cb.from_user.id))
    if not ok:
        return
    devices, limit = result

    if not devices:
        await cb.answer()
        await cb.message.answer(
            "📱 <b>Ваши устройства</b>\n\n"
            "Пока ни одного подключённого устройства не зарегистрировано.\n\n"
            "Устройство появляется здесь после первого подключения через приложение.",
            parse_mode="HTML",
            reply_markup=back_to_devices_keyboard(),
        )
        return

    counter = f"{len(devices)} из {limit}" if limit else str(len(devices))
    lines = "\n".join(f"• {escape(device_label(device))}" for device in devices)
    await cb.answer()
    await cb.message.answer(
        f"📱 <b>Ваши устройства ({counter})</b>\n\n"
        f"{lines}\n\n"
        "Нажмите на устройство, чтобы отключить его и освободить место.",
        parse_mode="HTML",
        reply_markup=devices_keyboard(devices),
    )


@router.callback_query(F.data.startswith("device_del:"))
async def confirm_device_delete(cb: CallbackQuery) -> None:
    token = cb.data.split(":", 1)[1]
    ok, result = await _panel_call(cb, get_devices(cb.from_user.id))
    if not ok:
        return

    devices, _limit = result
    device = next(
        (d for d in devices if d.get("hwid") and device_token(str(d["hwid"])) == token), None
    )
    if device is None:
        await cb.answer("Это устройство уже отключено.", show_alert=True)
        return

    await cb.answer()
    await cb.message.answer(
        f"❌ <b>Отключить устройство?</b>\n\n"
        f"<b>{escape(device_label(device))}</b>\n\n"
        "На нём VPN перестанет работать до следующего подключения по ссылке. "
        "Место в лимите устройств освободится сразу.",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard(f"device_del_ok:{token}", confirm_text="❌ Отключить"),
    )


@router.callback_query(F.data.startswith("device_del_ok:"))
async def do_device_delete(cb: CallbackQuery) -> None:
    token = cb.data.split(":", 1)[1]
    ok, result = await _panel_call(cb, get_devices(cb.from_user.id))
    if not ok:
        return

    devices, _limit = result
    # Re-resolved against a fresh list rather than trusted from the callback:
    # the confirmation screen may have sat in the chat for a long time.
    device = next(
        (d for d in devices if d.get("hwid") and device_token(str(d["hwid"])) == token), None
    )
    if device is None:
        await cb.answer("Это устройство уже отключено.", show_alert=True)
        return

    label = device_label(device)
    ok, _ = await _panel_call(cb, delete_device(cb.from_user.id, str(device["hwid"])))
    if not ok:
        return

    await cb.answer("Устройство отключено")
    await cb.message.answer(
        f"✅ <b>Устройство отключено</b>\n\n{escape(label)}",
        parse_mode="HTML",
        reply_markup=back_to_devices_keyboard(),
    )


# -- subscription link reset -----------------------------------------------


@router.callback_query(F.data == "sub_reset")
async def confirm_subscription_reset(cb: CallbackQuery) -> None:
    await cb.answer()
    await cb.message.answer(
        "🔄 <b>Сбросить ссылку подключения?</b>\n\n"
        "Текущая ссылка перестанет работать. На <b>всех</b> устройствах "
        "придётся заново импортировать новую — до этого VPN на них не подключится.\n\n"
        "Это нужно, если ссылка попала к посторонним.",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard("sub_reset_ok", confirm_text="🔄 Сбросить ссылку"),
    )


@router.callback_query(F.data == "sub_reset_ok")
async def do_subscription_reset(cb: CallbackQuery) -> None:
    ok, url = await _panel_call(cb, reset_subscription_url(cb.from_user.id))
    if not ok:
        return

    await cb.answer("Ссылка обновлена")
    if not url:
        # The rotation itself succeeded -- saying otherwise would send the user
        # round again on an already-dead old link.
        await cb.message.answer(
            "✅ <b>Ссылка обновлена</b>\n\n"
            "Откройте своё устройство в меню, чтобы получить новую ссылку.",
            parse_mode="HTML",
            reply_markup=back_to_devices_keyboard(),
        )
        return

    await cb.message.answer(
        "✅ <b>Ссылка обновлена</b>\n\n"
        "Новая ссылка подключения:\n\n"
        f"<code>{escape(url, quote=True)}</code>\n\n"
        "Импортируйте её заново на каждом устройстве — "
        "или откройте своё устройство в меню и следуйте инструкции.",
        parse_mode="HTML",
        reply_markup=back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )

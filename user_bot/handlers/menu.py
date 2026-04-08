import asyncio
import logging
import os
import re
import time
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.remnawave.vpn_service import (
    create_vpn_user_by_telegram_id,
    ensure_vpn_profile_created_if_missing,
)
from app.config.settings import get_remnawave_settings
from data.db_utils import (
    create_user_record,
    get_lte_remaining_bytes,
    get_user_by_id,
    update_subscription_expire,
    update_user_email,
    update_telegram_tag,
    user_in_db,
)
from handlers.email_state import EmailCaptureState
from handlers.constants import SECONDS_IN_DAY, TRIAL_DAYS
from handlers.keyboards import help_menu_keyboard, os_keyboard, pay_keyboard


router = Router()
STATUS_CHANNEL_URL = os.getenv("STATUS_CHANNEL_URL", "https://t.me/nitratex1")
CHANNEL_INFO_TEXT_MD = (
    "📢 *У нас есть Telegram\\-канал бота*\n\n"
    "Там публикуем информацию о техработах, блокировках и важных обновлениях\\.\n"
    "Подпишитесь, чтобы быть в курсе\\."
)


def _format_gb_from_bytes(value: int) -> str:
    gb = max(0, int(value)) / (1024 ** 3)
    return f"{gb:.2f}".rstrip("0").rstrip(".")


def _channel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL)]]
    )


def _email_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить", callback_data="change_email_cancel")]]
    )


def _is_valid_email(value: str) -> bool:
    value = value.strip()
    if len(value) > 254:
        return False
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    return re.fullmatch(pattern, value) is not None


async def _render_main_menu(
    chat_obj: types.Message | types.CallbackQuery,
) -> None:
    """
    Показывает главное меню. Работает как из Message, так и из CallbackQuery.
    """
    is_cb = isinstance(chat_obj, types.CallbackQuery)
    bot = chat_obj.bot
    chat_id = chat_obj.message.chat.id if is_cb else chat_obj.chat.id
    orig_msg = chat_obj.message if is_cb else chat_obj
    user = chat_obj.from_user
    user_id = user.id
    username = user.username or ""
    now_ts = int(time.time())

    if is_cb:
        await chat_obj.answer()

    if not user_in_db(user_id):
        create_user_record(user_id, username)
        create_vpn_user_by_telegram_id(user_id, TRIAL_DAYS)
        ensure_vpn_profile_created_if_missing(user_id)
        expire_ts = now_ts + TRIAL_DAYS * SECONDS_IN_DAY
        update_subscription_expire(user_id, expire_ts)

        msg = await bot.send_message(
            chat_id,
            "🔧 Создаём профиль…",
            parse_mode="HTML",
        )
        await asyncio.sleep(0.6)
        await msg.edit_text("🌐 Загружаем сервера…", parse_mode="HTML")
        await asyncio.sleep(0.6)
        await msg.edit_text(
            (
                "<b>👋 Привет!</b>\n\n"
                f"🎉 Вам открыт <b>бесплатный доступ</b> на {TRIAL_DAYS} дней.\n\n"
                "Выберите своё устройство:"
            ),
            parse_mode="HTML",
            reply_markup=os_keyboard(),
        )

        try:
            await orig_msg.delete()
        except Exception:
            pass
        return

    row = get_user_by_id(user_id)
    sub_ends = row["subscription_ends"] if isinstance(row, dict) else row[2]
    days_left = max(0, (sub_ends - now_ts) // SECONDS_IN_DAY)
    expire_date = datetime.utcfromtimestamp(sub_ends).strftime("%d.%m.%Y")

    if username:
        update_telegram_tag(user_id, username)

    if sub_ends > now_ts:
        lte_settings = get_remnawave_settings()
        lte_remaining_bytes = get_lte_remaining_bytes(
            user_id,
            free_gb=lte_settings.lte_free_gb_per_30d,
        )
        lte_remaining_gb = _format_gb_from_bytes(lte_remaining_bytes)
        header = (
            f"<b>👋 С возвращением, @{username}!</b>\n\n"
            if username else "<b>👋 С возвращением!</b>\n\n"
        )
        body = (
            "🛡 <b>Ваша подписка активна!</b>\n\n"
            f"📅 <b>Действует до:</b> {expire_date}\n"
            f"⏳ <b>Осталось:</b> {days_left} дн.\n\n"
            f"📶 <b>LTE трафик доступно:</b> {lte_remaining_gb} ГБ\n\n"
        )
        await bot.send_message(
            chat_id,
            header + body,
            parse_mode="HTML",
            reply_markup=os_keyboard(),
        )
    else:
        await bot.send_message(
            chat_id,
            (
                "🚫 Ваша подписка закончилась.\n\n"
                "Чтобы продолжить пользоваться VPN-сервисом, продлите подписку:"
            ),
            parse_mode="HTML",
            reply_markup=pay_keyboard(),
        )


async def _send_help_menu(
    target: types.Message | types.CallbackQuery,
    *,
    as_edit: bool = False,
) -> None:
    text_md = (
        "❓ *Помощь и поддержка*\n\n"
        "Выберите нужный раздел:"
    )

    if as_edit:
        await target.message.edit_text(text_md, reply_markup=help_menu_keyboard(), parse_mode="MarkdownV2")
        await target.answer()
    else:
        await target.answer(text_md, reply_markup=help_menu_keyboard(), parse_mode="MarkdownV2")


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    await _render_main_menu(message)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_main_menu(cb)


@router.message(Command("help"))
async def help_cmd(message: types.Message) -> None:
    await _send_help_menu(message, as_edit=False)


@router.callback_query(F.data == "help")
async def help_cb(cb: types.CallbackQuery) -> None:
    await _send_help_menu(cb, as_edit=False)


@router.callback_query(F.data == "change_email")
async def change_email_cb(cb: types.CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(EmailCaptureState.waiting_email)
    await state.update_data(email_forced=False)
    await cb.message.answer(
        "✉️ Введите новый email в формате example@mail.com",
        reply_markup=_email_cancel_keyboard(),
    )


@router.callback_query(F.data == "change_email_cancel")
async def change_email_cancel_cb(cb: types.CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    state_data = await state.get_data()
    if state_data.get("email_forced"):
        await cb.message.answer(
            "❗️Сейчас отменить нельзя — сначала укажите email."
        )
        return
    await state.clear()
    await cb.message.answer("✅ Изменение email отменено.")


@router.message(Command("channel"))
async def channel_cmd(message: types.Message) -> None:
    await message.answer(
        CHANNEL_INFO_TEXT_MD,
        parse_mode="MarkdownV2",
        reply_markup=_channel_keyboard(),
    )


@router.message(EmailCaptureState.waiting_email)
async def capture_email(message: types.Message, state: FSMContext) -> None:
    email = (message.text or "").strip()
    state_data = await state.get_data()
    forced = bool(state_data.get("email_forced"))
    if not _is_valid_email(email):
        if forced:
            await message.answer(
                "❌ Некорректный email.\n"
                "Введите адрес в формате example@mail.com"
            )
        else:
            await message.answer(
                "❌ Некорректный email.\n"
                "Введите адрес в формате example@mail.com",
                reply_markup=_email_cancel_keyboard(),
            )
        return

    update_user_email(message.from_user.id, email.lower())
    await state.clear()
    await message.answer(
        "✅ Email сохранён.\n"
        "Теперь вы сможете зайти на сайт и управлять подпиской даже при блокировке Telegram."
    )

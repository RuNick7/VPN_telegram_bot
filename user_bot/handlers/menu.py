import asyncio
import logging
import os
import re
import time
from datetime import datetime

import requests
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
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
from handlers.keyboards import (
    free_mode_keyboard,
    help_menu_keyboard,
    os_keyboard,
    pay_keyboard,
)


router = Router()
STATUS_CHANNEL_URL = os.getenv("STATUS_CHANNEL_URL", "https://t.me/nitratex1")
CHANNEL_INFO_TEXT_MD = (
    "📢 *У нас есть Telegram\\-канал бота*\n\n"
    "Там публикуем информацию о техработах, блокировках и важных обновлениях\\.\n"
    "Подпишитесь, чтобы быть в курсе\\."
)

WEB_API_BASE_URL = os.getenv("WEB_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
WEB_INTERNAL_SECRET = os.getenv("WEB_INTERNAL_SECRET", "")
WEB_LINK_TIMEOUT_SECONDS = 10.0

WEB_LINK_TOKEN_RE = re.compile(r"^web_([A-Za-z0-9_-]+)$")


def _confirm_web_link_token_sync(
    *,
    token: str,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> tuple[bool, str]:
    if not WEB_INTERNAL_SECRET:
        return False, "WEB_INTERNAL_SECRET is not configured"
    try:
        response = requests.post(
            f"{WEB_API_BASE_URL}/api/internal/telegram-link/confirm",
            json={
                "token": token,
                "telegram_id": int(telegram_id),
                "username": username or "",
                "first_name": first_name or "",
                "last_name": last_name or "",
            },
            headers={"X-Kaira-Internal-Secret": WEB_INTERNAL_SECRET},
            timeout=WEB_LINK_TIMEOUT_SECONDS,
        )
        if response.status_code == 200:
            return True, "ok"
        if response.status_code == 404:
            return False, "expired"
        return False, f"HTTP {response.status_code}"
    except Exception as exc:
        logging.warning("[web-link] failed to confirm token: %s", exc)
        return False, str(exc)


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

    user_already_in_db = await asyncio.to_thread(user_in_db, user_id)
    if not user_already_in_db:
        await asyncio.to_thread(create_user_record, user_id, username)
        await asyncio.to_thread(create_vpn_user_by_telegram_id, user_id, TRIAL_DAYS)
        await asyncio.to_thread(ensure_vpn_profile_created_if_missing, user_id)
        expire_ts = now_ts + TRIAL_DAYS * SECONDS_IN_DAY
        await asyncio.to_thread(update_subscription_expire, user_id, expire_ts)

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

    row = await asyncio.to_thread(get_user_by_id, user_id)
    sub_ends = row["subscription_ends"] if isinstance(row, dict) else row[2]
    days_left = max(0, (sub_ends - now_ts) // SECONDS_IN_DAY)
    expire_date = datetime.utcfromtimestamp(sub_ends).strftime("%d.%m.%Y")

    if username:
        await asyncio.to_thread(update_telegram_tag, user_id, username)

    if sub_ends > now_ts:
        lte_settings = get_remnawave_settings()
        lte_remaining_bytes = await asyncio.to_thread(
            get_lte_remaining_bytes,
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
        # Subscription expired -> user has been demoted to the FREE squad with
        # a single free server. They can keep using the bot for free, or
        # upgrade by buying a subscription (which will restore them to all
        # paid servers automatically).
        await bot.send_message(
            chat_id,
            (
                "🚫 <b>Ваша подписка закончилась.</b>\n\n"
                "🆓 Сейчас вы в <b>бесплатном режиме</b>: доступен 1 сервер без оплаты.\n"
                "💳 Купите подписку, чтобы вернуть полный доступ ко всем серверам и LTE.\n\n"
                "Выберите устройство, чтобы подключиться к бесплатному серверу, либо нажмите «Купить подписку»:"
            ),
            parse_mode="HTML",
            reply_markup=free_mode_keyboard(),
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
async def cmd_start(message: types.Message, command: CommandObject | None = None) -> None:
    if command and command.args:
        match = WEB_LINK_TOKEN_RE.match(command.args.strip())
        if match:
            token = match.group(1)
            user_already_in_db = await asyncio.to_thread(user_in_db, message.from_user.id)
            if not user_already_in_db:
                await asyncio.to_thread(
                    create_user_record,
                    message.from_user.id,
                    message.from_user.username or "",
                )
                await asyncio.to_thread(
                    create_vpn_user_by_telegram_id, message.from_user.id, TRIAL_DAYS
                )
                await asyncio.to_thread(
                    ensure_vpn_profile_created_if_missing, message.from_user.id
                )
                trial_expire_ts = int(time.time()) + TRIAL_DAYS * SECONDS_IN_DAY
                await asyncio.to_thread(
                    update_subscription_expire, message.from_user.id, trial_expire_ts
                )
            ok, reason = await asyncio.to_thread(
                _confirm_web_link_token_sync,
                token=token,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            if ok:
                await message.answer(
                    "✅ Аккаунт успешно привязан к сайту.\n\n"
                    "Вернитесь на вкладку с сайтом — мы продолжим оттуда автоматически."
                )
            else:
                await message.answer(
                    "⚠️ Ссылка для привязки сайта недействительна или устарела.\n"
                    "Откройте сайт заново и нажмите «Привязать Telegram» ещё раз."
                )
            return
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


@router.message(Command("news"))
async def news_cmd(message: types.Message) -> None:
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

    await asyncio.to_thread(update_user_email, message.from_user.id, email.lower())
    await state.clear()
    await message.answer(
        "✅ Email сохранён.\n"
        "Теперь вы сможете зайти на сайт и управлять подпиской даже при блокировке Telegram."
    )

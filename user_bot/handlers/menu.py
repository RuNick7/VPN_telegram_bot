import asyncio
import logging
import time
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.services.remnawave.vpn_service import (
    create_vpn_user_by_telegram_id,
    ensure_vpn_profile_created_if_missing,
)
from data.db_utils import (
    create_user_record,
    get_user_by_id,
    update_subscription_expire,
    update_telegram_tag,
    user_in_db,
)
from handlers.constants import SECONDS_IN_DAY, TRIAL_DAYS
from handlers.keyboards import help_menu_keyboard, os_keyboard, pay_keyboard


router = Router()


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
        header = (
            f"<b>👋 С возвращением, @{username}!</b>\n\n"
            if username else "<b>👋 С возвращением!</b>\n\n"
        )
        body = (
            "🛡 <b>Ваша подписка активна!</b>\n\n"
            f"📅 <b>Действует до:</b> {expire_date}\n"
            f"⏳ <b>Осталось:</b> {days_left} дн.\n\n"
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
    await _send_help_menu(cb, as_edit=True)

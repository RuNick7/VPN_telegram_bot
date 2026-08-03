import asyncio
import logging
import re
import time
from datetime import datetime, timezone

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.remnawave.vpn_service import create_vpn_user, ensure_vpn_profile_exists
from tgvpn_shared.settings import get_settings
from tgvpn_shared.db import LteRepository, UserRepository
from tgvpn_shared.lte_quota import TRAFFIC_LABEL, format_traffic, remaining_now
from handlers.email_link import offer_keyboard, offer_text, send_confirmation, should_offer
from handlers.email_state import EmailCaptureState
from handlers.constants import SECONDS_IN_DAY, trial_days
from handlers.keyboards import help_menu_keyboard, os_keyboard, pay_keyboard


router = Router()
_users = UserRepository()
_lte = LteRepository()
STATUS_CHANNEL_URL = get_settings().status_channel_url
CHANNEL_INFO_TEXT_MD = (
    "📢 *У нас есть Telegram\\-канал бота*\n\n"
    "Там публикуем информацию о техработах, блокировках и важных обновлениях\\.\n"
    "Подпишитесь, чтобы быть в курсе\\."
)


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


async def _traffic_line(telegram_id: int, *, subscription_active: bool) -> str:
    """
    One line on whitelist traffic for the devices menu, or nothing at all.

    Omitted entirely when quotas are switched off: a figure nothing meters
    would be fiction. When the subscription has lapsed it says so instead of
    quoting gigabytes -- the quota monitor only grants these servers to paying
    users, so a number there would advertise access the user does not have.

    Never raises. This is the one screen that must always open, and a balance
    is not worth failing /start over.
    """
    settings = get_settings()
    if not settings.lte_enabled:
        return ""

    try:
        state = await _lte.get_state(telegram_id)
    except Exception as exc:
        logging.warning("[TRAFFIC] Не удалось прочитать остаток для %s: %s", telegram_id, exc)
        return ""
    if state is None:
        return ""

    if not subscription_active:
        return f"📶 <b>{TRAFFIC_LABEL}:</b> вернётся после продления\n\n"

    left = remaining_now(
        state=state,
        global_free_gb=settings.lte_free_gb_per_cycle,
        cycle_seconds=settings.lte_cycle_seconds,
        now=int(time.time()),
    )
    if left <= 0:
        return f"📶 <b>{TRAFFIC_LABEL}:</b> закончился — докупить /traffic\n\n"
    return f"📶 <b>{TRAFFIC_LABEL}:</b> {format_traffic(left)}\n\n"


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

    user_already_in_db = await _users.user_in_db(user_id)
    if not user_already_in_db:
        # Our database first, the panel second. If the panel call fails the
        # user holds their trial with no profile yet, and
        # `ensure_vpn_profile_exists` builds it from the days already
        # recorded. The other order left the panel granting the days while our
        # row still said zero -- and nothing revisited it, because the next
        # /start sees the row and skips this branch entirely.
        days = trial_days()
        await _users.create_user_record(user_id, username)
        # Records the grant as well as the date, so the account cannot later
        # collect the signup half of the trial a second time through the site.
        await _users.grant_signup_trial_by_telegram_id(user_id, days)
        await create_vpn_user(user_id, days)
        await ensure_vpn_profile_exists(user_id)

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
                f"🎉 Вам открыт <b>бесплатный доступ</b> на {days} дн.\n\n"
                + await _traffic_line(user_id, subscription_active=True)
                + "Выберите своё устройство:"
            ),
            parse_mode="HTML",
            reply_markup=os_keyboard(),
        )

        try:
            await orig_msg.delete()
        except Exception:
            pass
        return

    row = await _users.get_user_by_id(user_id)
    sub_ends = int(row["subscription_ends"] or 0)
    days_left = max(0, (sub_ends - now_ts) // SECONDS_IN_DAY)
    expire_date = datetime.fromtimestamp(sub_ends, tz=timezone.utc).strftime("%d.%m.%Y")

    if username:
        await _users.update_telegram_tag(user_id, username)

    header = (
        f"<b>👋 С возвращением, @{username}!</b>\n\n"
        if username else "<b>👋 С возвращением!</b>\n\n"
    )

    if sub_ends > now_ts:
        body = (
            "🛡 <b>Ваша подписка активна!</b>\n\n"
            f"📅 <b>Действует до:</b> {expire_date}\n"
            f"⏳ <b>Осталось:</b> {days_left} дн.\n\n"
        )
    else:
        # An expired subscription is a downgrade, not a lockout: the device
        # menu still opens and the connection link still works, just on the
        # free servers. Showing only a "renew" button here used to leave a
        # lapsed user with no way to reach their link at all.
        body = (
            "🔓 <b>Подписка закончилась</b>\n\n"
            "Доступ сохранён на <b>бесплатных серверах</b> — ссылка подключения работает.\n"
            "Продлите подписку, чтобы вернуть все серверы:\n\n"
        )

    traffic = await _traffic_line(user_id, subscription_active=sub_ends > now_ts)

    await bot.send_message(
        chat_id,
        header + body + traffic + "Выберите своё устройство:",
        parse_mode="HTML",
        reply_markup=os_keyboard(),
    )

    await _offer_email_bonus_once(chat_id, row)


async def _offer_email_bonus_once(chat_id: int, row) -> None:
    """
    Offer the email bonus, at most once per account, ever.

    Sent as its own message after the menu rather than folded into it: the menu
    is what the customer came for, and burying an offer in it would push the
    device buttons below the fold for everyone. The flag is written before the
    message is sent, so a send that fails costs the offer rather than repeating
    it on every /start.
    """
    if not await should_offer(row):
        return
    try:
        await _users.mark_bonus_offer_shown_in_bot(str(row["id"]))
        await bot.send_message(
            chat_id, offer_text(), parse_mode="HTML", reply_markup=offer_keyboard()
        )
    except Exception as exc:
        logging.warning("Could not offer the email bonus to %s: %s", row["id"], exc)


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
    await cb.message.answer(
        "✉️ Введите новый email в формате example@mail.com",
        reply_markup=_email_cancel_keyboard(),
    )


@router.callback_query(F.data == "change_email_cancel")
async def change_email_cancel_cb(cb: types.CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await cb.message.answer("✅ Изменение email отменено.")


@router.callback_query(F.data == "bonus_offer_dismiss")
async def bonus_offer_dismiss_cb(cb: types.CallbackQuery) -> None:
    """
    "Не сейчас" on the email offer.

    Recorded rather than only acknowledged, so the same answer holds on the
    website: it is one offer about one account, and being asked again in a
    different window is the thing that makes it feel like nagging.
    """
    await cb.answer()
    row = await _users.get_user_by_id(cb.from_user.id)
    if row is not None:
        await _users.dismiss_bonus_offer(str(row["id"]))
    try:
        await cb.message.edit_text(
            "Хорошо. Привязать почту можно в любой момент — /help → «Изменить email».",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("channel"))
async def channel_cmd(message: types.Message) -> None:
    await message.answer(
        CHANNEL_INFO_TEXT_MD,
        parse_mode="MarkdownV2",
        reply_markup=_channel_keyboard(),
    )


@router.message(EmailCaptureState.waiting_email)
async def capture_email(message: types.Message, state: FSMContext) -> None:
    """
    Save an email the user chose to give us.

    Nothing forces this any more. A middleware used to block every command a
    day after signup until an address was typed -- taxing everyone to solve a
    problem only the website had. The website identifies people by our own id
    now, so the bot does not need an address to function. Giving one is still
    useful (it is how you sign in on the site), so the entry point stays,
    opt-in.
    """
    email = (message.text or "").strip()
    if not _is_valid_email(email):
        await message.answer(
            "❌ Некорректный email.\n"
            "Введите адрес в формате example@mail.com",
            reply_markup=_email_cancel_keyboard(),
        )
        return

    row = await _users.get_user_by_id(message.from_user.id)
    if row is None:
        await state.clear()
        await message.answer("❌ Аккаунт не найден. Откройте /start и попробуйте снова.")
        return

    await state.clear()
    # Nothing is written yet. The address becomes a sign-in route on the
    # website, so it is only saved once a letter sent to it has been opened --
    # this used to save whatever was typed, which meant one typo handed a
    # stranger's mailbox the ability to request a login link for this account.
    await message.answer(
        await send_confirmation(str(row["id"]), email.lower()), parse_mode="HTML"
    )

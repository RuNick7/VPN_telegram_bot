import time
import asyncio
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from datetime import datetime

from tgvpn_shared.settings import get_settings
from tgvpn_shared.db import UserRepository

logger = logging.getLogger(__name__)
_users = UserRepository()

SECONDS_DAY = 86_400
STATUS_CHANNEL_URL = get_settings().status_channel_url

REMINDER_TEXT = (
    "⚠️ Ваша подписка истекает через 24 часа!\n\n"
    "Чтобы не потерять доступ — продлите её."
)

pay_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💳 Продлить", callback_data="subscription_tariffs")]
    ]
)


async def send_reminders(bot: Bot):
    """Отправить напоминания и проставить flag reminded=1."""
    users = await _users.get_users_with_expiring_subscriptions()
    if not users:
        logging.info("[INFO] Нет пользователей для напоминания.")
        return

    for u in users:
        # The Telegram ID *is* the chat id for a private chat. This used to
        # read `u["chat_id"]`, a column the query does not select and the table
        # does not have -- so every user was skipped with a warning and the
        # expiry reminder had never once been delivered.
        chat_id = u.get("telegram_id")
        if not chat_id:
            logging.warning("[WARN] Нет telegram_id у строки напоминания: %r", u)
            continue

        try:
            if not await _users.mark_reminded_if_needed(u["telegram_id"]):
                continue
            await bot.send_message(chat_id, REMINDER_TEXT, reply_markup=pay_kb)
            logging.info(f"[INFO] Напоминание отправлено {chat_id}")
        except Exception as e:
            await _users.set_reminded_flag(u["telegram_id"], False)
            logging.error(f"[ERROR] Не удалось отправить {chat_id}: {e}")


async def reminders_scheduler(bot: Bot):
    """
    Запускает hour-loop напоминаний и nurture-цепочек.
    """
    while True:
        now_ts = int(time.time())
        try:
            logger.debug("Запуск hourly reminders в %s", datetime.now())
            await send_reminders(bot)
            # One stage per pass, newest first. Running them in ascending order
            # meant each step handed the same person straight to the next: a
            # user sitting at stage 0 -- anyone who joined before the campaign
            # existed -- collected all four messages within one second of each
            # other. Descending, a stage advanced this hour is no longer a
            # candidate for the stage above it until the next.
            await send_nurture_3(bot, now_ts)
            await send_nurture_2(bot, now_ts)
            await send_nurture_1(bot, now_ts)
            await send_nurture_channel(bot, now_ts)
            logger.debug("Hourly reminders выполнены успешно")
        except Exception:
            logger.exception("Ошибка в hourly reminders")
        await asyncio.sleep(3600)


async def send_nurture_1(bot: Bot, now_ts: int):
    users = await _users.get_users_for_nurture(now_ts, target_stage=2, days_after=3)
    if not users:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="☰ Открыть меню", callback_data="main_menu")]]
    )
    text_md = (
        "💡 *Полезные команды бота*\n\n"
        "• `/help` — помощь\n"
        "• `/promo` — использовать промокоды\n"
        "• `/gift` — подарить подписку\n"
        "• `/ref` — реферальная программа\n"
        "• `/pay` — продлить подписку"
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=2, kb=kb)


async def send_nurture_2(bot: Bot, now_ts: int):
    users = await _users.get_users_for_nurture(now_ts, target_stage=3, days_after=10)
    if not users:
        return
    text_md = (
        "👥 *Реферальная программа*\n\n"
        "Приглашайте друзей и получайте бонусные дни\\!\n"
        "Команда для участия: `/ref`"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Перейти к /ref", callback_data="referral_info")]]
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=3, kb=kb)


async def send_nurture_3(bot: Bot, now_ts: int):
    users = await _users.get_users_for_nurture(now_ts, target_stage=4, days_after=25)
    if not users:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Продлить", callback_data="subscription_tariffs")]]
    )
    text_md = (
        "⏳ *Скоро закончится бесплатный период\\!*\n\n"
        "Продлите подписку заранее командой `/pay` "
        "или нажмите кнопку ниже\\."
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=4, kb=kb)


async def send_nurture_channel(bot: Bot, now_ts: int):
    users = await _users.get_users_for_nurture(now_ts, target_stage=1, days_after=1)
    if not users:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL)]]
    )
    text_md = (
        "📢 *У нас есть Telegram\\-канал бота*\n\n"
        "Там публикуем информацию о техработах, блокировках и важных обновлениях\\.\n"
        "Подпишитесь, чтобы быть в курсе\\."
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=1, kb=kb)


async def _broadcast_and_mark(bot: Bot, rows, text, next_stage: int, kb):
    succeeded = []
    for row in rows:
        try:
            await bot.send_message(row["telegram_id"], text,
                                   parse_mode="MarkdownV2",
                                   reply_markup=kb)
            succeeded.append(row["telegram_id"])
        except Exception as e:
            logging.error(f"Nurture send fail {row['telegram_id']}: {e}")

    await _users.update_nurture_stage(succeeded, next_stage)

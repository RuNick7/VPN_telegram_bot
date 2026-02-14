import time
import asyncio
import logging, sqlite3
import os
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from datetime import datetime
from data.db_utils import get_db

logger = logging.getLogger(__name__)

SECONDS_DAY = 86_400
STATUS_CHANNEL_URL = os.getenv("STATUS_CHANNEL_URL", "https://t.me/nitratex1")

REMINDER_TEXT = (
    "⚠️ Ваша подписка истекает через 24 часа!\n\n"
    "Чтобы не потерять доступ — продлите её."
)

pay_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💳 Продлить", callback_data="subscription_tariffs")]
    ]
)

def get_users_with_expiring_subscriptions():
    """
    Возвращает список пользователей, у которых подписка истекает в ближайшие 24 часа
    и которым ещё не было отправлено напоминание.
    """
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = int(time.time())
        cursor.execute("""
            SELECT telegram_id, subscription_ends, telegram_tag
            FROM subscription
            WHERE reminded = 0 AND subscription_ends BETWEEN ? AND ?
        """, (now, now + 86400))
        rows = cursor.fetchall()

    # Преобразуем в список словарей и подставим chat_id = telegram_id
    return [
        {
            **dict(row),
            "chat_id": row["telegram_id"]  # используем telegram_id как chat_id
        }
        for row in rows
    ]

def _set_reminded_flag(telegram_id: int, value: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE subscription SET reminded = ? WHERE telegram_id = ?",
            (value, telegram_id),
        )
        conn.commit()

def _mark_reminded_if_needed(telegram_id: int) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE subscription SET reminded = 1 WHERE telegram_id = ? AND reminded = 0",
            (telegram_id,),
        )
        conn.commit()
        return cur.rowcount > 0

async def send_reminders(bot: Bot):
    """Отправить напоминания и проставить flag reminded=1."""
    users = get_users_with_expiring_subscriptions()
    if not users:
        logging.info("[INFO] Нет пользователей для напоминания.")
        return

    for u in users:
        chat_id = u.get("chat_id")
        if not chat_id:
            logging.warning(f"[WARN] chat_id отсутствует ({u['telegram_id']})")
            continue

        try:
            if not _mark_reminded_if_needed(u["telegram_id"]):
                continue
            await bot.send_message(chat_id, REMINDER_TEXT, reply_markup=pay_kb)
            logging.info(f"[INFO] Напоминание отправлено {chat_id}")
        except Exception as e:
            _set_reminded_flag(u["telegram_id"], 0)
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
            await send_nurture_channel(bot, now_ts)
            await send_nurture_1(bot, now_ts)
            await send_nurture_2(bot, now_ts)
            await send_nurture_3(bot, now_ts)
            logger.debug("Hourly reminders выполнены успешно")
        except Exception:
            logger.exception("Ошибка в hourly reminders")
        await asyncio.sleep(3600)

def get_users_for_nurture(now_ts: int, target_stage: int, days_after: int):
    """
    Возвращает пользователей, у которых nurture_stage == target_stage-1
    и со дня создания прошло нужное число суток.
    """
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT telegram_id
            FROM subscription
            WHERE nurture_stage = ?
              AND created_at <= ?
            """,
            (target_stage - 1, now_ts - days_after * SECONDS_DAY)
        )
        return cur.fetchall()

async def send_nurture_1(bot: Bot, now_ts: int):
    users = get_users_for_nurture(now_ts, target_stage=2, days_after=3)
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
    users = get_users_for_nurture(now_ts, target_stage=3, days_after=10)
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
    users = get_users_for_nurture(now_ts, target_stage=4, days_after=25)
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
    users = get_users_for_nurture(now_ts, target_stage=1, days_after=1)
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

def update_stage(telegram_ids: list[int], stage: int):
    if not telegram_ids:
        return
    q_marks = ",".join("?" * len(telegram_ids))
    with get_db() as conn:
        conn.execute(
            f"UPDATE subscription SET nurture_stage = ? WHERE telegram_id IN ({q_marks})",
            (stage, *telegram_ids)
        )
        conn.commit()

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

    update_stage(succeeded, next_stage)

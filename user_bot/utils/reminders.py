import time
import asyncio
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from datetime import datetime

from tgvpn_shared.settings import get_settings
from tgvpn_shared.db import UserRepository

from handlers.constants import PRICES, trial_days
from handlers.utils import escape_markdown_v2

logger = logging.getLogger(__name__)
_users = UserRepository()

SECONDS_DAY = 86_400
STATUS_CHANNEL_URL = get_settings().status_channel_url

# Read from the same table the checkout charges from, so a message cannot
# quote a price the customer will not be offered.
MAX_REFERRAL_TIER = max(PRICES)
BASE_MONTHLY_PRICE = PRICES[0][1]
BEST_TIER_MONTHLY_PRICE = PRICES[MAX_REFERRAL_TIER][1]

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
            for send in NURTURE_SENDERS:
                await send(bot, now_ts)
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
    """
    Day 10: what inviting people is actually worth.

    It used to promise "бонусные дни". Referrals do not pay days -- they move
    the customer down the price table, which is a different and rather better
    offer. Somebody who invited five friends expecting free time and got a
    cheaper renewal has been misled by us in writing.
    """
    users = await _users.get_users_for_nurture(now_ts, target_stage=5, days_after=10)
    if not users:
        return
    text_md = (
        "👥 *Приглашайте друзей — подписка дешевеет*\n\n"
        "Каждый приглашённый снижает цену вашей подписки\\. "
        "На пятом друге месяц стоит "
        f"{escape_markdown_v2(str(BEST_TIER_MONTHLY_PRICE))} ₽ вместо "
        f"{escape_markdown_v2(str(BASE_MONTHLY_PRICE))} ₽ — и остаётся таким\\.\n\n"
        "Ваша ссылка и счётчик приглашённых: `/ref`"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Моя ссылка", callback_data="referral_info")]]
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=5, kb=kb)


async def send_nurture_3(bot: Bot, now_ts: int):
    """
    Sent one day before the free period runs out, whatever it currently is.

    It used to go out on day 25 and open with "скоро закончится бесплатный
    период". With a seven-day trial that arrived eighteen days after the
    period had ended, to somebody who by then had either paid or left.
    """
    users = await _users.get_users_for_nurture(
        now_ts, target_stage=4, days_after=max(1, trial_days() - 1)
    )
    if not users:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Посмотреть тарифы", callback_data="subscription_tariffs")]]
    )
    text_md = (
        "⏳ *Бесплатный период заканчивается*\n\n"
        "Чтобы доступ не прервался, продлите подписку — от "
        f"{escape_markdown_v2(str(BASE_MONTHLY_PRICE))} ₽ за месяц\\.\n\n"
        "Оплата картой, подписка продлевается сразу\\."
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=4, kb=kb)


async def send_nurture_site(bot: Bot, now_ts: int):
    """
    Day 5: there is a website, and it is the same account.

    Worth its own message because nothing else says it. Somebody who arrived
    through the bot has no reason to suspect a cabinet exists, and the two
    things it does better than a chat -- reading a QR on the machine you are
    setting up, and having an address that can recover the account if the
    Telegram one is lost -- are exactly what they will want later.
    """
    site = get_settings().web_base_url.strip().rstrip("/")
    if not site:
        return
    users = await _users.get_users_for_nurture(now_ts, target_stage=3, days_after=5)
    if not users:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🌐 Открыть личный кабинет", url=site + "/app")]]
    )
    text_md = (
        "🌐 *У сервиса есть сайт*\n\n"
        f"{escape_markdown_v2(site)} — тот же аккаунт, что и здесь\\.\n\n"
        "На большом экране удобнее: настройка устройств с QR\\-кодом, "
        "история оплат и подарки в одном месте\\.\n\n"
        "Вход по почте — и если Telegram однажды потеряется, "
        "аккаунт останется с вами\\."
    )
    await _broadcast_and_mark(bot, users, text_md, next_stage=3, kb=kb)


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


# The chain, highest stage first.
#
# Two rules hold it together. Stages ascend with the day they fire on, because
# a stage gates the one above it -- numbering the day-5 message above the
# day-10 one would make it wait for a message a week further out. And they run
# in descending order, because ascending meant each step handed the person it
# had just advanced straight to the next: anybody at stage 0, which is everyone
# who joined before the chain existed, collected the whole series in one second.
#
#   1 — day 1                 канал
#   2 — day 3                 команды
#   3 — day 5                 сайт
#   4 — day TRIAL_DAYS - 1    бесплатный период кончается
#   5 — day 10                рефералы
NURTURE_SENDERS = (
    send_nurture_2,        # stage 5
    send_nurture_3,        # stage 4
    send_nurture_site,     # stage 3
    send_nurture_1,        # stage 2
    send_nurture_channel,  # stage 1
)

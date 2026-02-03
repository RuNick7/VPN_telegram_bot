import re
import time

from handlers.constants import PRICES, SECONDS_IN_DAY
from data.db_utils import get_db


def escape_markdown_v2(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    escape_chars = r"*_[]()~`>#+-=|{}.!<>"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def days_to_unixtime(days: int) -> int:
    """Смещение от текущего момента на N дней."""
    return int(time.time()) + days * SECONDS_IN_DAY


def unixtime_to_days(ts: int) -> int:
    """Сколько дней осталось до ts от «сейчас» (>=0)."""
    return max(0, (ts - int(time.time())) // SECONDS_IN_DAY)


def get_subscription_price(months: int, referred_people: int) -> int:
    if months not in (1, 3, 6, 12):
        raise ValueError("Недопустимый срок подписки")
    tier = min(referred_people, 5)
    return PRICES[tier][months]


def get_subscription_info(telegram_id: int) -> dict | None:
    """
    Получает информацию о подписке для указанного telegram_id из базы данных.
    Возвращает словарь вида:
        {
            "subscription_ends": int,         # время окончания подписки (Unix timestamp)
            "gifted_subscriptions": int,       # количество подаренных подписок
            "referred_people": int             # количество приведённых людей
        }
    Если записи нет, возвращает None.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT subscription_ends, gifted_subscriptions, referred_people FROM subscription WHERE telegram_id = ?",
            (telegram_id,),
        )
        result = cursor.fetchone()
    if result:
        return {
            "subscription_ends": result[0],
            "gifted_subscriptions": result[1],
            "referred_people": result[2],
        }
    return None

import sqlite3
import time
import logging
import random
import string
import os
from pathlib import Path

from dotenv import load_dotenv
from contextlib import contextmanager

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT_DIR / ".env")
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "subscription.db"
DB_PATH = os.getenv("DB_PATH", str(DEFAULT_DB_PATH))
_db = None

@contextmanager
def get_db():
    if not DB_PATH:
        raise RuntimeError("DB_PATH is not set and default path is empty.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
    finally:
        conn.close()

def insert_new_user(telegram_id, username, subscription_ends, referrer_tag, is_referred, referred_people, gifted_subscriptions):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscription (
                telegram_id, telegram_tag, subscription_ends, 
                referrer_tag, is_referred, referred_people, 
                gifted_subscriptions
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            telegram_id, username, subscription_ends,
            referrer_tag, int(is_referred), referred_people,
            gifted_subscriptions
        ))
        conn.commit()

def generate_gift_code(length=6):
    return "GIFT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_gift_promo(code: str, days: int, creator_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO promo_codes (code, type, value, is_active, one_time, creator_id)
            VALUES (?, 'gift', ?, 1, 1, ?)
            """,
            (code, days, creator_id)
        )
        conn.commit()

def increment_gifted_subscriptions(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE subscription SET gifted_subscriptions = gifted_subscriptions + 1 WHERE telegram_id = ?",
            (user_id,)
        )
        conn.commit()

def get_user_by_tag(tag: str):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscription WHERE telegram_tag = ?", (tag,))
        return cursor.fetchone()

def get_user_by_id(user_id: int):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscription WHERE telegram_id = ?", (user_id,))
        return cursor.fetchone()

def set_referrer_tag(user_id: int, tag: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE subscription SET referrer_tag = ? WHERE telegram_id = ?", (tag, user_id))
        conn.commit()

def award_referral(referrer_tag: str, telegram_id: int) -> bool:
    """
    Atomically marks user as referred and increments referrer count.
    Returns True if referral was applied, False if already referred.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE subscription SET is_referred = 1 WHERE telegram_id = ? AND is_referred = 0",
            (telegram_id,),
        )
        if cursor.rowcount:
            cursor.execute(
                "UPDATE subscription SET referred_people = referred_people + 1 WHERE telegram_tag = ?",
                (referrer_tag,),
            )
            conn.commit()
            return True
        conn.commit()
        return False

def get_promo_by_code(code: str):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promo_codes WHERE code = ?", (code.upper(),))
        return cursor.fetchone()

def has_any_usage(code: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM promo_usage WHERE code = ?", (code,))
        result = cursor.fetchone()
        return result is not None

def has_used_promo(code: str, user_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM promo_usage WHERE code = ? AND telegram_id = ?", (code, user_id))
        return cursor.fetchone() is not None

def save_promo_usage(code: str, user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO promo_usage (code, telegram_id) VALUES (?, ?)", (code, user_id))
        conn.commit()

def update_telegram_tag(telegram_id: int, telegram_tag: str):
    """Обновляет поле telegram_tag для пользователя по telegram_id."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE subscription SET telegram_tag = ? WHERE telegram_id = ?", (telegram_tag, telegram_id))
        conn.commit()

def user_in_db(telegram_id: int) -> bool:
    """
    Проверяем, есть ли запись о пользователе с таким telegram_id в таблице subscription.
    Возвращает True, если запись найдена, False — если нет.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM subscription WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return row is not None

def create_user_record(telegram_id: int, username: str):
    now_ts = int(time.time())
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO subscription
                (telegram_id, telegram_tag,
                 subscription_ends, reminded,
                 nurture_stage, created_at)
            VALUES (?, ?, 0, 0, 0, ?)
            """,
            (telegram_id, username, now_ts)
        )
        conn.commit()


def update_payment_status(payment_id: str, new_status: str):
    """
    Обновляет поле `status` для записи, у которой payment_id = payment_id.
    Заодно можно проставить updated_at = текущее время, чтобы знать, когда произошли изменения.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Обновляем статус и время обновления
        cursor.execute("""
            UPDATE payments
            SET status = ?
            WHERE payment_id = ?
        """, (new_status, payment_id))

        conn.commit()

def get_payment_status(payment_id: str) -> str | None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM payments WHERE payment_id = ?", (payment_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def update_subscription_expire(telegram_id: int, new_expire: int):
    """
    Обновляет поле subscription_ends для пользователя в таблице subscription по telegram_id.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscription SET subscription_ends = ? WHERE telegram_id = ?",
                (new_expire, telegram_id)
            )
            conn.commit()
            logging.info("Срок подписки обновлён для telegram_id: %s, новый expire: %s", telegram_id, new_expire)
    except Exception as e:
        logging.error("Ошибка обновления срока подписки для telegram_id %s: %s", telegram_id, e)

"""Subscription database helpers (user_bot SQLite)."""

from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import aiosqlite

from app.config.settings import settings


def _get_db_path() -> Path:
    db_path = Path(settings.user_bot_db_path).expanduser()
    if not db_path.is_absolute():
        db_path = (Path(settings.base_dir) / db_path).resolve()
    else:
        db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


async def _ensure_subscription_table(db: aiosqlite.Connection, db_path: Path) -> None:
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='subscription'"
    )
    exists = await cursor.fetchone()
    if not exists:
        raise RuntimeError(f"no such table: subscription (db: {db_path})")


async def insert_subscription_user(
    telegram_id: int,
    subscription_ends: datetime,
    telegram_tag: str = "",
    referrer_tag: Optional[str] = None,
    gifted_subscriptions: int = 0,
    referred_people: int = 0,
    is_referred: int = 0,
    nurture_stage: int = 0,
    reminded: int = 0,
) -> None:
    """Insert user into user_bot subscription DB."""
    db_path = _get_db_path()

    subscription_ends_ts = int(subscription_ends.replace(tzinfo=timezone.utc).timestamp())
    created_at_ts = int(datetime.now(timezone.utc).timestamp())

    query = """
        INSERT INTO subscription (
            telegram_id,
            subscription_ends,
            reminded,
            telegram_tag,
            gifted_subscriptions,
            referred_people,
            referrer_tag,
            is_referred,
            nurture_stage,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        await db.execute(
            query,
            (
                telegram_id,
                subscription_ends_ts,
                reminded,
                telegram_tag,
                gifted_subscriptions,
                referred_people,
                referrer_tag or "",
                is_referred,
                nurture_stage,
                created_at_ts,
            ),
        )
        await db.commit()


async def upsert_subscription_expire(
    telegram_id: int,
    subscription_ends: datetime,
) -> None:
    """Update subscription expiry for a user in user_bot DB."""
    db_path = _get_db_path()

    subscription_ends_ts = int(subscription_ends.replace(tzinfo=timezone.utc).timestamp())
    created_at_ts = int(datetime.now(timezone.utc).timestamp())

    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute(
            "SELECT id FROM subscription WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                """
                UPDATE subscription
                SET subscription_ends = ?,
                    reminded = 0,
                    telegram_tag = '',
                    gifted_subscriptions = 0,
                    referred_people = 0,
                    referrer_tag = NULL,
                    is_referred = 0,
                    nurture_stage = 0,
                    created_at = ?
                WHERE telegram_id = ?
                """,
                (subscription_ends_ts, created_at_ts, telegram_id),
            )
        else:
            await db.execute(
                """
                INSERT INTO subscription (
                    telegram_id,
                    subscription_ends,
                    reminded,
                    telegram_tag,
                    gifted_subscriptions,
                    referred_people,
                    referrer_tag,
                    is_referred,
                    nurture_stage,
                    created_at
                )
                VALUES (?, ?, 0, '', 0, 0, NULL, 0, 0, ?)
                """,
                (telegram_id, subscription_ends_ts, created_at_ts),
            )
        await db.commit()


async def upsert_subscription_telegram_id(
    old_telegram_id: int,
    new_telegram_id: int,
    subscription_ends: Optional[datetime] = None,
) -> None:
    """Update telegram_id in subscription DB; insert if missing."""
    db_path = _get_db_path()

    created_at_ts = int(datetime.now(timezone.utc).timestamp())
    subscription_ends_ts = None
    if subscription_ends is not None:
        subscription_ends_ts = int(subscription_ends.replace(tzinfo=timezone.utc).timestamp())

    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute(
            "SELECT id FROM subscription WHERE telegram_id = ?",
            (old_telegram_id,),
        )
        row = await cursor.fetchone()
        if row:
            if subscription_ends_ts is None:
                await db.execute(
                    """
                    UPDATE subscription
                    SET telegram_id = ?,
                        reminded = 0,
                        telegram_tag = '',
                        gifted_subscriptions = 0,
                        referred_people = 0,
                        referrer_tag = NULL,
                        is_referred = 0,
                        nurture_stage = 0,
                        created_at = ?
                    WHERE telegram_id = ?
                    """,
                    (new_telegram_id, created_at_ts, old_telegram_id),
                )
            else:
                await db.execute(
                    """
                    UPDATE subscription
                    SET telegram_id = ?,
                        subscription_ends = ?,
                        reminded = 0,
                        telegram_tag = '',
                        gifted_subscriptions = 0,
                        referred_people = 0,
                        referrer_tag = NULL,
                        is_referred = 0,
                        nurture_stage = 0,
                        created_at = ?
                    WHERE telegram_id = ?
                    """,
                    (new_telegram_id, subscription_ends_ts, created_at_ts, old_telegram_id),
                )
        else:
            if subscription_ends_ts is None:
                subscription_ends_ts = created_at_ts
            await db.execute(
                """
                INSERT INTO subscription (
                    telegram_id,
                    subscription_ends,
                    reminded,
                    telegram_tag,
                    gifted_subscriptions,
                    referred_people,
                    referrer_tag,
                    is_referred,
                    nurture_stage,
                    created_at
                )
                VALUES (?, ?, 0, '', 0, 0, NULL, 0, 0, ?)
                """,
                (new_telegram_id, subscription_ends_ts, created_at_ts),
            )
        await db.commit()


async def delete_subscription_user(telegram_id: int) -> bool:
    """Delete user from subscription DB by telegram_id."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute(
            "DELETE FROM subscription WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_subscription_user_by_username(username: str) -> bool:
    """Delete user from subscription DB by telegram_tag or telegram_id."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute(
            "DELETE FROM subscription WHERE telegram_tag = ? OR telegram_id = ?",
            (username, username),
        )
        await db.commit()
        return cursor.rowcount > 0


async def insert_promo_code(
    code: str,
    promo_type: str,
    value: int,
    one_time: int,
    is_active: int = 1,
) -> None:
    """Insert promo code into user_bot DB."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        await db.execute(
            """
            INSERT INTO promo_codes (code, type, value, is_active, one_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code, promo_type, value, is_active, one_time),
        )
        await db.commit()


async def delete_promo_code(code: str) -> bool:
    """Delete promo code by code. Returns True if deleted."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        await db.commit()
        return cursor.rowcount > 0


async def get_all_telegram_ids() -> list[int]:
    """Fetch all telegram_id values from subscription DB."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute("SELECT telegram_id FROM subscription")
        rows = await cursor.fetchall()
    return [int(row[0]) for row in rows if row and row[0] is not None]


async def get_inactive_telegram_ids_for_cleanup(inactive_days: int = 30) -> list[int]:
    """
    Return telegram_ids whose latest subscription_end is older than inactive_days.

    Uses MAX(subscription_ends) per telegram_id to avoid false positives
    in case of duplicate rows.
    """
    db_path = _get_db_path()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    cutoff_ts = now_ts - inactive_days * 24 * 60 * 60
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        cursor = await db.execute(
            """
            SELECT telegram_id
            FROM subscription
            WHERE telegram_id IS NOT NULL
            GROUP BY telegram_id
            HAVING MAX(subscription_ends) <= ?
            """,
            (cutoff_ts,),
        )
        rows = await cursor.fetchall()
    return [int(row[0]) for row in rows if row and row[0] is not None]


async def get_subscription_rows_by_telegram_id(telegram_id: int) -> list[dict]:
    """Fetch all subscription rows by telegram_id."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await _ensure_subscription_table(db, db_path)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                id,
                telegram_id,
                telegram_tag,
                subscription_ends,
                reminded,
                referrer_tag,
                is_referred,
                referred_people,
                gifted_subscriptions,
                nurture_stage,
                created_at
            FROM subscription
            WHERE telegram_id = ?
            ORDER BY id DESC
            """,
            (telegram_id,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]

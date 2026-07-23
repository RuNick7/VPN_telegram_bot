"""
Repository for the `users` table — replaces user_bot/data/db_utils.py's
subscription-table functions, admin_bot/app/services/subscription_db.py, and
user_bot/handlers/utils.py's get_subscription_info.

Phase 1 keeps the Python-facing API on Unix epoch seconds (int) for
subscription_ends/created_at, matching every existing call site's arithmetic
(`now_ts + N*86400`, `sub_ends > now_ts`, ...) exactly — only the storage
column type changes to TIMESTAMPTZ. Queries convert epoch<->timestamptz in
SQL so returned rows behave identically to the old sqlite3.Row objects.
"""

from __future__ import annotations

from typing import Optional

import asyncpg

from .pool import get_pool

_EPOCH_SELECT = """
    id,
    telegram_id,
    telegram_tag,
    email,
    remnawave_uuid,
    merged_into,
    EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends,
    referrer_tag,
    is_referred,
    referred_people,
    gifted_subscriptions,
    reminded,
    nurture_stage,
    EXTRACT(EPOCH FROM created_at)::bigint AS created_at
"""


class UserRepository:
    async def insert_new_user(
        self,
        telegram_id: int,
        username: str,
        subscription_ends: int,
        referrer_tag: str | None,
        is_referred: bool,
        referred_people: int,
        gifted_subscriptions: int,
    ) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO users (
                telegram_id, telegram_tag, subscription_ends,
                referrer_tag, is_referred, referred_people, gifted_subscriptions
            ) VALUES ($1, $2, to_timestamp($3), $4, $5, $6, $7)
            """,
            telegram_id, username, subscription_ends,
            referrer_tag, bool(is_referred), referred_people, gifted_subscriptions,
        )

    async def create_user_record(self, telegram_id: int, username: str) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO users (telegram_id, telegram_tag, subscription_ends, reminded, nurture_stage, created_at)
            VALUES ($1, $2, to_timestamp(0), FALSE, 0, now())
            """,
            telegram_id, username,
        )

    async def get_user_by_id(self, telegram_id: int) -> Optional[asyncpg.Record]:
        """Despite the name (kept from db_utils.py for call-site compatibility),
        looks up by telegram_id, not the internal `id`."""
        pool = await get_pool()
        return await pool.fetchrow(
            f"SELECT {_EPOCH_SELECT} FROM users WHERE telegram_id = $1",
            telegram_id,
        )

    async def get_user_by_tag(self, tag: str) -> Optional[asyncpg.Record]:
        pool = await get_pool()
        return await pool.fetchrow(
            f"SELECT {_EPOCH_SELECT} FROM users WHERE telegram_tag = $1",
            tag,
        )

    async def get_subscription_info(self, telegram_id: int) -> Optional[dict]:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends,
                gifted_subscriptions,
                referred_people
            FROM users WHERE telegram_id = $1
            """,
            telegram_id,
        )
        return dict(row) if row else None

    async def get_subscription_rows_by_telegram_id(self, telegram_id: int) -> list[dict]:
        """telegram_id is unique in the new schema, so this returns at most one
        row — kept as a list for call-site compatibility with the old
        (pre-unique) SQLite version."""
        row = await self.get_user_by_id(telegram_id)
        return [dict(row)] if row else []

    async def user_in_db(self, telegram_id: int) -> bool:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT 1 FROM users WHERE telegram_id = $1", telegram_id)
        return row is not None

    async def update_user_email(self, telegram_id: int, email: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET email = $1 WHERE telegram_id = $2",
            email.strip(), telegram_id,
        )

    async def set_referrer_tag(self, telegram_id: int, tag: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET referrer_tag = $1 WHERE telegram_id = $2",
            tag, telegram_id,
        )

    async def award_referral(self, referrer_tag: str, telegram_id: int) -> bool:
        """Atomically marks user as referred and increments referrer count.
        Returns True if referral was applied, False if already referred."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                claimed_id = await conn.fetchval(
                    "UPDATE users SET is_referred = TRUE WHERE telegram_id = $1 AND is_referred = FALSE RETURNING id",
                    telegram_id,
                )
                if claimed_id is None:
                    return False
                await conn.execute(
                    "UPDATE users SET referred_people = referred_people + 1 WHERE telegram_tag = $1",
                    referrer_tag,
                )
                return True

    async def update_telegram_tag(self, telegram_id: int, telegram_tag: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET telegram_tag = $1 WHERE telegram_id = $2",
            telegram_tag, telegram_id,
        )

    async def update_subscription_expire(self, telegram_id: int, new_expire: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET subscription_ends = to_timestamp($1) WHERE telegram_id = $2",
            new_expire, telegram_id,
        )

    # --- admin_bot-side operations (formerly subscription_db.py) ---

    async def insert_subscription_user(
        self,
        telegram_id: int,
        subscription_ends: int,
        telegram_tag: str = "",
        referrer_tag: str | None = None,
        gifted_subscriptions: int = 0,
        referred_people: int = 0,
        is_referred: bool = False,
        nurture_stage: int = 0,
        reminded: bool = False,
    ) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO users (
                telegram_id, subscription_ends, reminded, telegram_tag,
                gifted_subscriptions, referred_people, referrer_tag, is_referred, nurture_stage
            ) VALUES ($1, to_timestamp($2), $3, $4, $5, $6, $7, $8, $9)
            """,
            telegram_id, subscription_ends, bool(reminded), telegram_tag,
            gifted_subscriptions, referred_people, referrer_tag or "", bool(is_referred), nurture_stage,
        )

    async def upsert_subscription_expire(self, telegram_id: int, subscription_ends: int) -> None:
        """Update subscription expiry only; never resets referrals/gifts/created_at."""
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE users SET subscription_ends = to_timestamp($1), reminded = FALSE WHERE telegram_id = $2",
            subscription_ends, telegram_id,
        )
        if result == "UPDATE 0":
            await pool.execute(
                """
                INSERT INTO users (telegram_id, subscription_ends, reminded, telegram_tag, referrer_tag)
                VALUES ($1, to_timestamp($2), FALSE, '', NULL)
                """,
                telegram_id, subscription_ends,
            )

    async def upsert_subscription_telegram_id(
        self,
        old_telegram_id: int,
        new_telegram_id: int,
        subscription_ends: int | None = None,
    ) -> None:
        """Change telegram_id (and optionally expiry) only; never resets other fields."""
        pool = await get_pool()
        if subscription_ends is None:
            result = await pool.execute(
                "UPDATE users SET telegram_id = $1, reminded = FALSE WHERE telegram_id = $2",
                new_telegram_id, old_telegram_id,
            )
        else:
            result = await pool.execute(
                "UPDATE users SET telegram_id = $1, subscription_ends = to_timestamp($2), reminded = FALSE WHERE telegram_id = $3",
                new_telegram_id, subscription_ends, old_telegram_id,
            )
        if result == "UPDATE 0":
            fallback_ends = subscription_ends if subscription_ends is not None else 0
            await pool.execute(
                """
                INSERT INTO users (telegram_id, subscription_ends, reminded, telegram_tag, referrer_tag)
                VALUES ($1, to_timestamp($2), FALSE, '', NULL)
                """,
                new_telegram_id, fallback_ends,
            )

    async def delete_subscription_user(self, telegram_id: int) -> bool:
        pool = await get_pool()
        result = await pool.execute("DELETE FROM users WHERE telegram_id = $1", telegram_id)
        return result != "DELETE 0"

    async def delete_subscription_user_by_username(self, username: str) -> bool:
        """Deletes by telegram_tag OR telegram_id (matching original semantics —
        `username` may actually be a numeric telegram_id passed as a string)."""
        pool = await get_pool()
        telegram_id_val: int | None
        try:
            telegram_id_val = int(username)
        except (TypeError, ValueError):
            telegram_id_val = None
        result = await pool.execute(
            "DELETE FROM users WHERE telegram_tag = $1 OR telegram_id = $2",
            username, telegram_id_val,
        )
        return result != "DELETE 0"

    async def get_all_telegram_ids(self) -> list[int]:
        pool = await get_pool()
        rows = await pool.fetch("SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL")
        return [int(row["telegram_id"]) for row in rows]

    async def get_inactive_telegram_ids_for_cleanup(self, inactive_days: int = 30) -> list[int]:
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT telegram_id FROM users
            WHERE telegram_id IS NOT NULL
              AND subscription_ends <= now() - ($1 * INTERVAL '1 day')
            """,
            inactive_days,
        )
        return [int(row["telegram_id"]) for row in rows]

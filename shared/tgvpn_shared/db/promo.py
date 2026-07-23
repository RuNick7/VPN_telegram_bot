"""Repository for `promo_codes`/`promo_usage` — replaces the promo functions in
user_bot/data/db_utils.py and admin_bot/app/services/subscription_db.py."""

from __future__ import annotations

import random
import string
from typing import Optional

import asyncpg

from .pool import get_pool


def generate_gift_code(length: int = 6) -> str:
    return "GIFT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class PromoRepository:
    async def create_gift_promo(self, code: str, days: int, creator_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO promo_codes (code, type, value, is_active, one_time, creator_id)
            VALUES ($1, 'gift', $2, TRUE, TRUE, $3)
            """,
            code, days, creator_id,
        )

    async def insert_promo_code(
        self,
        code: str,
        promo_type: str,
        value: int,
        one_time: bool,
        is_active: bool = True,
    ) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO promo_codes (code, type, value, is_active, one_time)
            VALUES ($1, $2, $3, $4, $5)
            """,
            code, promo_type, value, bool(is_active), bool(one_time),
        )

    async def delete_promo_code(self, code: str) -> bool:
        pool = await get_pool()
        result = await pool.execute("DELETE FROM promo_codes WHERE code = $1", code)
        return result != "DELETE 0"

    async def get_promo_by_code(self, code: str) -> Optional[asyncpg.Record]:
        pool = await get_pool()
        return await pool.fetchrow(
            "SELECT * FROM promo_codes WHERE code = $1", code.upper()
        )

    async def has_any_usage(self, code: str) -> bool:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT 1 FROM promo_usage WHERE code = $1", code)
        return row is not None

    async def has_used_promo(self, code: str, telegram_id: int) -> bool:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT 1 FROM promo_usage WHERE code = $1 AND telegram_id = $2",
            code, telegram_id,
        )
        return row is not None

    async def save_promo_usage(self, code: str, telegram_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO promo_usage (code, telegram_id) VALUES ($1, $2)",
            code, telegram_id,
        )

    async def try_claim_promo_usage(self, code: str, telegram_id: int, *, one_time: bool) -> bool:
        """
        Atomically records promo usage BEFORE crediting days.

        For one_time codes (gift), the claim only succeeds for the first
        user ever; for multi-use codes, once per user. Returns False if the
        code is already claimed. Roll back a failed credit with
        release_promo_usage().
        """
        pool = await get_pool()
        if one_time:
            claimed = await pool.fetchval(
                """
                INSERT INTO promo_usage (code, telegram_id)
                SELECT $1, $2
                WHERE NOT EXISTS (SELECT 1 FROM promo_usage WHERE code = $1)
                RETURNING id
                """,
                code, telegram_id,
            )
        else:
            claimed = await pool.fetchval(
                """
                INSERT INTO promo_usage (code, telegram_id)
                SELECT $1, $2
                WHERE NOT EXISTS (
                    SELECT 1 FROM promo_usage WHERE code = $1 AND telegram_id = $2
                )
                RETURNING id
                """,
                code, telegram_id,
            )
        return claimed is not None

    async def release_promo_usage(self, code: str, telegram_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM promo_usage WHERE code = $1 AND telegram_id = $2",
            code, telegram_id,
        )

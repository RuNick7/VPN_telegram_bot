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
    async def create_gift_promo(
        self,
        code: str,
        days: int,
        creator_id: int | None,
        creator_user_id: str | None = None,
    ) -> None:
        """
        Record a gift somebody has just paid for.

        Both handles are stored. `creator_id` is a Telegram ID and is what an
        operator recognises in support; `creator_user_id` is the internal id
        every account has, and it is the one that matters -- it is how the
        buyer's own gifts are found so the site can show them the code, and it
        is what stops a buyer with no Telegram from redeeming their own gift.
        Before it existed a website purchase recorded no creator at all.
        """
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO promo_codes
                (code, type, value, is_active, one_time, creator_id, creator_user_id)
            VALUES ($1, 'gift', $2, TRUE, TRUE, $3, $4::uuid)
            """,
            code, days, creator_id, creator_user_id,
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

    async def recent_gifts(self, limit: int = 20) -> list[asyncpg.Record]:
        """
        The latest gifts, with who bought each and whether it has been used.

        Redemption is read from `promo_usage` rather than stored on the code,
        because that table is what the claim actually writes -- a second copy
        of "has this been used" could disagree with the one the redemption
        path enforces.
        """
        pool = await get_pool()
        return await pool.fetch(
            """
            SELECT
                p.code,
                p.value                              AS days,
                p.created_at,
                p.creator_id,
                buyer.email                          AS buyer_email,
                buyer.telegram_tag                   AS buyer_tag,
                buyer.telegram_id                    AS buyer_telegram_id,
                usage.used_at                        AS redeemed_at,
                taker.telegram_tag                   AS taker_tag,
                taker.email                          AS taker_email
            FROM promo_codes p
            LEFT JOIN users buyer ON buyer.id = p.creator_user_id
            LEFT JOIN LATERAL (
                SELECT user_id, used_at FROM promo_usage
                WHERE code = p.code ORDER BY used_at LIMIT 1
            ) usage ON TRUE
            LEFT JOIN users taker ON taker.id = usage.user_id
            WHERE p.type = 'gift'
            ORDER BY p.created_at DESC
            LIMIT $1
            """,
            limit,
        )

    async def gift_stats(self) -> dict:
        """How many gifts exist and how many have been used."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*)                                            AS total,
                COUNT(*) FILTER (
                    WHERE EXISTS (SELECT 1 FROM promo_usage u WHERE u.code = p.code)
                )                                                   AS redeemed,
                COUNT(*) FILTER (
                    WHERE p.created_at >= now() - INTERVAL '30 days'
                )                                                   AS last_month
            FROM promo_codes p
            WHERE p.type = 'gift'
            """
        )
        return dict(row) if row else {}

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
        Claim a code for a Telegram user. Thin wrapper over the id-based form.

        Kept because every bot call site has a telegram_id in hand and nothing
        else; the row it resolves to is what actually owns the claim.
        """
        row = await self._user_id_for_telegram(telegram_id)
        if row is None:
            return False
        return await self.try_claim_promo_usage_by_user_id(
            code, row, one_time=one_time, telegram_id=telegram_id
        )

    async def try_claim_promo_usage_by_user_id(
        self, code: str, user_id: str, *, one_time: bool, telegram_id: int | None = None
    ) -> bool:
        """
        Atomically record promo usage BEFORE crediting days.

        Claiming first is what stops a one-time code being redeemed twice by
        two people racing each other: the loser's insert finds the code taken
        and nothing is credited. If crediting then fails, `release_promo_usage`
        puts it back.

        Keyed on `users.id`, so an account with no Telegram -- someone who
        signed up on the website, and the most likely person to be handed a
        gift link -- can redeem exactly like anyone else. `telegram_id` is
        still stored when we have one, purely so support can recognise the row.
        """
        pool = await get_pool()
        if one_time:
            claimed = await pool.fetchval(
                """
                INSERT INTO promo_usage (code, telegram_id, user_id)
                SELECT $1, $2, $3::uuid
                WHERE NOT EXISTS (SELECT 1 FROM promo_usage WHERE code = $1)
                RETURNING id
                """,
                code, telegram_id, user_id,
            )
        else:
            claimed = await pool.fetchval(
                """
                INSERT INTO promo_usage (code, telegram_id, user_id)
                SELECT $1, $2, $3::uuid
                WHERE NOT EXISTS (
                    SELECT 1 FROM promo_usage WHERE code = $1 AND user_id = $3::uuid
                )
                RETURNING id
                """,
                code, telegram_id, user_id,
            )
        return claimed is not None

    async def release_promo_usage(self, code: str, telegram_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM promo_usage WHERE code = $1 AND telegram_id = $2",
            code, telegram_id,
        )

    async def release_promo_usage_by_user_id(self, code: str, user_id: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM promo_usage WHERE code = $1 AND user_id = $2::uuid", code, user_id
        )

    async def _user_id_for_telegram(self, telegram_id: int) -> Optional[str]:
        pool = await get_pool()
        row = await pool.fetchval(
            "SELECT id::text FROM users WHERE telegram_id = $1", telegram_id
        )
        return str(row) if row else None

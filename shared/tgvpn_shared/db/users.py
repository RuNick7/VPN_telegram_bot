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
    remnawave_username,
    merged_into,
    EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends,
    referrer_tag,
    is_referred,
    referred_people,
    gifted_subscriptions,
    reminded,
    nurture_stage,
    lte_paid_balance_bytes,
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

    # -- internal identity -------------------------------------------------
    #
    # Everything above addresses a user by telegram_id, which is what the bot
    # has in hand. The methods below address them by our own `id`, which is
    # what the website has -- and what a person who has never touched Telegram
    # has instead.

    async def get_user_by_uuid(self, user_id: str) -> Optional[asyncpg.Record]:
        """
        Look a user up by internal id, following any merge.

        A merged account's id stays valid on purpose: a website session, a
        payment already in flight at YooKassa, or a link handed out yesterday
        all carry the old id, and every one of them must land on the surviving
        account rather than on a dead row. The recursion is bounded because a
        merge only ever points at a row that is not itself merged.
        """
        pool = await get_pool()
        return await pool.fetchrow(
            f"""
            WITH RECURSIVE chain AS (
                SELECT id, merged_into, 0 AS depth FROM users WHERE id = $1
                UNION ALL
                SELECT u.id, u.merged_into, chain.depth + 1
                FROM users u JOIN chain ON u.id = chain.merged_into
                WHERE chain.depth < 8
            )
            SELECT {_EPOCH_SELECT} FROM users
            WHERE id = (SELECT id FROM chain WHERE merged_into IS NULL LIMIT 1)
            """,
            user_id,
        )

    async def set_subscription_ends(self, user_id: str, subscription_ends: int) -> bool:
        """
        Set a user's expiry, addressed by internal id.

        The telegram_id-keyed variants above cannot serve a website account,
        which has none. Clears `reminded` for the same reason they do: a new
        period should be able to send its own expiry warning.
        """
        pool = await get_pool()
        result = await pool.execute(
            """
            UPDATE users
            SET subscription_ends = to_timestamp($1::bigint), reminded = FALSE
            WHERE id = $2::uuid
            """,
            subscription_ends, user_id,
        )
        return result != "UPDATE 0"

    async def set_panel_identity(
        self, user_id: str, *, remnawave_uuid: str | None, remnawave_username: str | None
    ) -> None:
        """
        Record which panel account belongs to this user.

        Called both when we create one and when a legacy lookup by
        `str(telegram_id)` succeeds -- backfilling on read is what retires the
        legacy path one user at a time, without a bulk rename against a live
        panel.
        """
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE users
            SET remnawave_uuid = $1::uuid, remnawave_username = $2
            WHERE id = $3::uuid
            """,
            remnawave_uuid, remnawave_username, user_id,
        )

    async def attach_telegram(
        self, user_id: str, telegram_id: int, telegram_tag: str
    ) -> bool:
        """
        Give a website account a Telegram identity.

        Only fills an empty slot: `telegram_id IS NULL` in the WHERE clause
        means a second link attempt cannot move an account off the Telegram
        user it already belongs to. Returns False when the account already had
        one, which the caller treats as "merge instead".
        """
        pool = await get_pool()
        result = await pool.execute(
            """
            UPDATE users SET telegram_id = $1, telegram_tag = $2
            WHERE id = $3::uuid AND telegram_id IS NULL
            """,
            telegram_id, telegram_tag or "", user_id,
        )
        return result != "UPDATE 0"

    async def apply_merge(self, plan) -> None:
        """
        Fold one account into another, in one transaction.

        `identity.plan_merge` decided the numbers; this only writes them. Both
        statements have to land together -- a survivor credited with the
        absorbed account's days while the absorbed row stays independently
        usable would double the time the user actually paid for.
        """
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE users SET
                        subscription_ends      = to_timestamp($1::bigint),
                        lte_paid_balance_bytes = $2::bigint,
                        gifted_subscriptions   = $3,
                        referred_people        = $4,
                        email                  = COALESCE(email, $5),
                        referrer_tag           = COALESCE(NULLIF(referrer_tag, ''), $6),
                        remnawave_uuid         = COALESCE(remnawave_uuid, $7::uuid),
                        remnawave_username     = COALESCE(remnawave_username, $8)
                    WHERE id = $9::uuid
                    """,
                    plan.subscription_ends,
                    plan.lte_paid_balance_bytes,
                    plan.gifted_subscriptions,
                    plan.referred_people,
                    plan.email,
                    plan.referrer_tag,
                    plan.adopt_panel_uuid,
                    plan.adopt_panel_username,
                    plan.survivor_id,
                )
                # The absorbed row keeps its own panel columns so an operator
                # can still find the leftover account; `merged_into` is what
                # takes it out of circulation.
                await connection.execute(
                    """
                    UPDATE users SET
                        merged_into            = $1::uuid,
                        telegram_id            = NULL,
                        subscription_ends      = to_timestamp(0),
                        lte_paid_balance_bytes = 0
                    WHERE id = $2::uuid
                    """,
                    plan.survivor_id, plan.absorbed_id,
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

    async def admin_set_referrer(
        self, telegram_id: int, tag: str | None, *, reset_awarded: bool = True
    ) -> bool:
        """
        Overwrite a user's referrer from the admin panel. Returns False if no
        such user.

        Unlike `set_referrer_tag` (the customer-facing path, which can only
        ever set a referrer once) this can also clear it -- pass None. By
        default it also clears `is_referred`, so a corrected referrer can still
        earn their bonus on the user's next payment; the old one keeps whatever
        was already credited, since un-crediting them could take a bonus away
        for an unrelated referral.
        """
        pool = await get_pool()
        if reset_awarded:
            result = await pool.execute(
                "UPDATE users SET referrer_tag = $1, is_referred = FALSE WHERE telegram_id = $2",
                tag, telegram_id,
            )
        else:
            result = await pool.execute(
                "UPDATE users SET referrer_tag = $1 WHERE telegram_id = $2",
                tag, telegram_id,
            )
        return result != "UPDATE 0"

    async def set_referred_people(self, telegram_id: int, count: int) -> int | None:
        """
        Set the "people this user invited" counter. Returns the new value, or
        None if there is no such user.

        This counter is not just a statistic -- it selects the user's price
        tier (see `get_subscription_price`), so an admin setting it is granting
        a discount.
        """
        pool = await get_pool()
        return await pool.fetchval(
            "UPDATE users SET referred_people = $1 WHERE telegram_id = $2 RETURNING referred_people",
            max(0, int(count)), telegram_id,
        )

    async def adjust_referred_people(self, telegram_id: int, delta: int) -> int | None:
        """
        Add `delta` to the invited-people counter, clamped at zero.

        Relative rather than absolute so two admins editing at once can't lose
        each other's change, and so "+3" doesn't require reading the current
        value first.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users
            SET referred_people = GREATEST(0, referred_people + $1)
            WHERE telegram_id = $2
            RETURNING referred_people
            """,
            int(delta), telegram_id,
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

    async def increment_gifted_subscriptions(self, telegram_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET gifted_subscriptions = gifted_subscriptions + 1 WHERE telegram_id = $1",
            telegram_id,
        )

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

    async def get_stats(self, expiring_within_days: int = 3) -> dict:
        """
        One-pass aggregate counts for the admin statistics screen.

        Everything is computed in a single query rather than one round trip
        per number, so the screen stays cheap as the user base grows.
        """
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*)                                              AS total,
                COUNT(*) FILTER (WHERE subscription_ends > now())     AS active,
                COUNT(*) FILTER (WHERE subscription_ends <= now())    AS expired,
                COUNT(*) FILTER (
                    WHERE subscription_ends > now()
                      AND subscription_ends <= now() + ($1 * INTERVAL '1 day')
                )                                                     AS expiring_soon,
                COUNT(*) FILTER (WHERE created_at >= now() - INTERVAL '1 day')   AS new_today,
                COUNT(*) FILTER (WHERE created_at >= now() - INTERVAL '7 days')  AS new_week,
                COUNT(*) FILTER (WHERE created_at >= now() - INTERVAL '30 days') AS new_month,
                COUNT(*) FILTER (WHERE email IS NOT NULL AND email <> '')        AS with_email,
                COUNT(*) FILTER (
                    WHERE referrer_tag IS NOT NULL AND referrer_tag <> ''
                )                                                     AS with_referrer,
                COUNT(*) FILTER (WHERE is_referred)                   AS referrals_awarded,
                COALESCE(SUM(referred_people), 0)                     AS referred_people,
                COALESCE(SUM(gifted_subscriptions), 0)                AS gifted_subscriptions
            FROM users
            """,
            expiring_within_days,
        )
        return dict(row) if row else {}

    async def get_payment_stats(self) -> dict:
        """Payment counts by state, for the same statistics screen."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*)                                          AS total,
                COUNT(*) FILTER (WHERE status = 'succeeded')      AS succeeded,
                COUNT(*) FILTER (WHERE status = 'processing')     AS processing,
                COUNT(*) FILTER (
                    WHERE status NOT IN ('succeeded', 'processing')
                )                                                 AS failed,
                COUNT(*) FILTER (
                    WHERE status = 'succeeded'
                      AND updated_at >= now() - INTERVAL '30 days'
                )                                                 AS succeeded_month
            FROM payments
            """
        )
        return dict(row) if row else {}

    async def get_subscription_ends_map(self) -> dict[int, int]:
        """
        Every user's expiry as `{telegram_id: epoch_seconds}`.

        One query for the whole table: the reconciliation sweep walks every
        panel user and would otherwise issue a lookup per user.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT telegram_id, EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends
            FROM users WHERE telegram_id IS NOT NULL
            """
        )
        return {int(row["telegram_id"]): int(row["subscription_ends"] or 0) for row in rows}

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

    async def get_inactive_users_for_cleanup(self, inactive_days: int = 30) -> list[dict]:
        """
        Long-lapsed users, with everything needed to find their panel account.

        Returns the stored panel handles alongside the Telegram ID because
        looking accounts up by `str(telegram_id)` alone would miss every one
        created after the identity rework -- those are named `u-<uuid>`, and
        they would silently never be cleaned up.

        `subscription_ends > to_timestamp(0)` excludes accounts that have
        never had a subscription at all: they have nothing in the panel to
        delete, and sweeping them up would only add noise to the report.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT telegram_id, remnawave_uuid, remnawave_username
            FROM users
            WHERE merged_into IS NULL
              AND subscription_ends > to_timestamp(0)
              AND subscription_ends <= now() - ($1 * INTERVAL '1 day')
            """,
            inactive_days,
        )
        return [dict(row) for row in rows]

    # --- reminders/nurture (formerly defined ad hoc in user_bot/utils/reminders.py) ---

    async def get_users_with_expiring_subscriptions(self) -> list[dict]:
        """Users whose subscription ends within the next 24h and haven't been reminded yet."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                telegram_id,
                EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends,
                telegram_tag
            FROM users
            WHERE reminded = FALSE
              AND subscription_ends BETWEEN now() AND now() + INTERVAL '1 day'
            """
        )
        return [{**dict(row), "chat_id": row["telegram_id"]} for row in rows]

    async def mark_reminded_if_needed(self, telegram_id: int) -> bool:
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE users SET reminded = TRUE WHERE telegram_id = $1 AND reminded = FALSE",
            telegram_id,
        )
        return result != "UPDATE 0"

    async def set_reminded_flag(self, telegram_id: int, value: bool) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET reminded = $1 WHERE telegram_id = $2",
            value, telegram_id,
        )

    async def get_users_for_nurture(self, now_ts: int, target_stage: int, days_after: int) -> list[asyncpg.Record]:
        """Users at nurture_stage == target_stage-1, created at least days_after days ago."""
        pool = await get_pool()
        cutoff_ts = now_ts - days_after * 86400
        return await pool.fetch(
            "SELECT telegram_id FROM users WHERE nurture_stage = $1 AND created_at <= to_timestamp($2)",
            target_stage - 1, cutoff_ts,
        )

    async def update_nurture_stage(self, telegram_ids: list[int], stage: int) -> None:
        if not telegram_ids:
            return
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET nurture_stage = $1 WHERE telegram_id = ANY($2::bigint[])",
            stage, telegram_ids,
        )

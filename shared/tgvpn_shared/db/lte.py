"""
LTE traffic quota state.

LTE is a metered squad: each cycle a user gets a free allowance, and can buy
extra traffic that carries over between cycles. This repository owns the
arithmetic of that balance.

The one rule that matters here: **the balance is only ever adjusted by a
delta, never overwritten with a value read earlier.** The traffic monitor
reads state, talks to the panel (slow), then writes back -- and a purchase
webhook can credit the user in between. An absolute write would silently
erase that purchase. `legacy-main` shipped exactly that bug before fixing it;
the delta shape here is what keeps it fixed.
"""

from __future__ import annotations

from typing import Optional

from .pool import get_pool

# Selects LTE state with timestamps as epoch seconds, matching the epoch-int
# convention the rest of this package uses.
_STATE_SELECT = """
    SELECT
        id::text AS id,
        telegram_id,
        lte_paid_balance_bytes,
        EXTRACT(EPOCH FROM lte_cycle_start)::bigint AS lte_cycle_start,
        lte_cycle_spent_bytes,
        lte_blocked,
        lte_last_usage_bytes,
        lte_free_gb_override,
        lte_low_traffic_notified_mb,
        squad_tier
    FROM users
"""


class LteRepository:
    """
    Per-user LTE quota balances and cycle state.

    Most methods come in two forms. The `telegram_id` ones are what the bot
    and the admin panel have in hand; the `_by_user_id` ones address the same
    row by our internal UUID, which is the *only* handle an account created on
    the website has. Without the second form the traffic monitor skipped those
    users entirely -- no metering, no blocking when the quota ran out, no
    low-traffic warnings.
    """

    async def get_state(self, telegram_id: int) -> Optional[dict]:
        pool = await get_pool()
        row = await pool.fetchrow(f"{_STATE_SELECT} WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None

    async def get_state_by_user_id(self, user_id: str) -> Optional[dict]:
        pool = await get_pool()
        row = await pool.fetchrow(f"{_STATE_SELECT} WHERE id = $1::uuid", user_id)
        return dict(row) if row else None

    async def start_cycle_if_unset_by_user_id(
        self, user_id: str, cycle_start: int
    ) -> Optional[dict]:
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE users SET lte_cycle_start = to_timestamp($1::bigint)
            WHERE id = $2::uuid AND lte_cycle_start IS NULL
            """,
            cycle_start, user_id,
        )
        return await self.get_state_by_user_id(user_id)

    async def roll_cycle_by_user_id(self, user_id: str, new_cycle_start: int) -> Optional[int]:
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users
            SET lte_cycle_start = to_timestamp($1::bigint),
                lte_cycle_spent_bytes = 0,
                lte_low_traffic_notified_mb = 0
            WHERE id = $2::uuid
            RETURNING EXTRACT(EPOCH FROM lte_cycle_start)::bigint
            """,
            new_cycle_start, user_id,
        )

    async def credit_balance_by_user_id(self, user_id: str, bytes_added: int) -> Optional[int]:
        """Additive, exactly like `credit_balance`; see that docstring."""
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users
            SET lte_paid_balance_bytes = lte_paid_balance_bytes + $1::bigint
            WHERE id = $2::uuid
            RETURNING lte_paid_balance_bytes
            """,
            max(0, int(bytes_added)), user_id,
        )

    async def consume_balance_by_user_id(
        self,
        user_id: str,
        *,
        spent_delta_bytes: int,
        cycle_spent_bytes: int,
        blocked: bool,
        last_usage_bytes: int,
    ) -> Optional[dict]:
        """Delta-based, exactly like `consume_balance`; see that docstring."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            UPDATE users
            SET lte_paid_balance_bytes = GREATEST(0::bigint, lte_paid_balance_bytes - $1::bigint),
                lte_cycle_spent_bytes  = GREATEST(0::bigint, $2::bigint),
                lte_blocked            = $3,
                lte_last_usage_bytes   = GREATEST(0::bigint, $4::bigint)
            WHERE id = $5::uuid
            RETURNING
                lte_paid_balance_bytes,
                lte_cycle_spent_bytes,
                lte_blocked,
                lte_last_usage_bytes
            """,
            max(0, int(spent_delta_bytes)),
            int(cycle_spent_bytes),
            bool(blocked),
            int(last_usage_bytes),
            user_id,
        )
        return dict(row) if row else None

    async def set_low_traffic_notified_by_user_id(self, user_id: str, threshold_mb: int) -> None:
        """
        `threshold_mb` is not clamped to non-negative: `lte_quota.EXHAUSTED`
        (-1) is a real, distinct value here, not an out-of-range one -- see
        that constant for why 0 cannot mean both "recovered" and "empty".
        """
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET lte_low_traffic_notified_mb = $1 WHERE id = $2::uuid",
            int(threshold_mb), user_id,
        )

    async def start_cycle_if_unset(self, telegram_id: int, cycle_start: int) -> Optional[dict]:
        """
        Give a user their first quota window, leaving an existing one alone.

        Returns the resulting state, or None if there is no such user.
        """
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE users SET lte_cycle_start = to_timestamp($1::bigint)
            WHERE telegram_id = $2 AND lte_cycle_start IS NULL
            """,
            cycle_start, telegram_id,
        )
        return await self.get_state(telegram_id)

    async def roll_cycle(self, telegram_id: int, new_cycle_start: int) -> Optional[int]:
        """
        Advance the quota window and reset spend within it.

        The purchased balance is deliberately *not* reset -- bought traffic is
        owned by the user, not lent for one cycle.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users
            SET lte_cycle_start = to_timestamp($1::bigint),
                lte_cycle_spent_bytes = 0,
                -- A fresh allowance means the previous cycle's low-traffic
                -- warnings no longer apply and should be able to fire again.
                lte_low_traffic_notified_mb = 0
            WHERE telegram_id = $2
            RETURNING EXTRACT(EPOCH FROM lte_cycle_start)::bigint
            """,
            new_cycle_start, telegram_id,
        )

    async def credit_balance(self, telegram_id: int, bytes_added: int) -> Optional[int]:
        """
        Add purchased traffic. Returns the new balance, or None if no such user.

        Additive by construction, so a purchase landing mid-monitor-pass is
        preserved rather than overwritten.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users
            SET lte_paid_balance_bytes = lte_paid_balance_bytes + $1::bigint
            WHERE telegram_id = $2
            RETURNING lte_paid_balance_bytes
            """,
            max(0, int(bytes_added)), telegram_id,
        )

    async def consume_balance(
        self,
        telegram_id: int,
        *,
        spent_delta_bytes: int,
        cycle_spent_bytes: int,
        blocked: bool,
        last_usage_bytes: int,
    ) -> Optional[dict]:
        """
        Record one monitor pass: subtract what was spent, store the readings.

        `spent_delta_bytes` is what this pass consumed, subtracted from
        whatever the balance is *now* -- not a recomputed absolute. That is the
        whole point: a top-up between the monitor's read and this write stays.
        """
        pool = await get_pool()
        # Every byte parameter is cast explicitly. Without it asyncpg infers a
        # type from context -- and `GREATEST(0, $2)` looks like int4 because of
        # the literal zero, so anything past 2 GB raised "value out of int32
        # range" instead of being stored.
        row = await pool.fetchrow(
            """
            UPDATE users
            SET lte_paid_balance_bytes = GREATEST(0::bigint, lte_paid_balance_bytes - $1::bigint),
                lte_cycle_spent_bytes  = GREATEST(0::bigint, $2::bigint),
                lte_blocked            = $3,
                lte_last_usage_bytes   = GREATEST(0::bigint, $4::bigint)
            WHERE telegram_id = $5
            RETURNING
                lte_paid_balance_bytes,
                lte_cycle_spent_bytes,
                lte_blocked,
                lte_last_usage_bytes
            """,
            max(0, int(spent_delta_bytes)),
            int(cycle_spent_bytes),
            bool(blocked),
            int(last_usage_bytes),
            telegram_id,
        )
        return dict(row) if row else None

    async def set_balance(self, telegram_id: int, total_bytes: int) -> Optional[int]:
        """
        Set the purchased balance outright. Returns the new value, or None if
        no such user.

        Absolute, unlike `credit_balance` -- this is the admin correcting a
        balance to a known figure, not a purchase being applied. It is
        therefore never used by the traffic monitor, whose read-modify-write
        cycle is exactly what the additive form protects.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users SET lte_paid_balance_bytes = GREATEST(0::bigint, $1::bigint)
            WHERE telegram_id = $2
            RETURNING lte_paid_balance_bytes
            """,
            int(total_bytes), telegram_id,
        )

    async def set_balance_by_user_id(self, user_id: str, total_bytes: int) -> Optional[int]:
        """`set_balance`, addressed by our own id -- see that docstring."""
        pool = await get_pool()
        return await pool.fetchval(
            """
            UPDATE users SET lte_paid_balance_bytes = GREATEST(0::bigint, $1::bigint)
            WHERE id = $2::uuid
            RETURNING lte_paid_balance_bytes
            """,
            int(total_bytes), user_id,
        )

    async def set_free_gb_override(self, telegram_id: int, gigabytes: int | None) -> bool:
        """
        Give one user a different monthly free allowance, or clear the override.

        `None` clears it, falling back to the global `LTE_FREE_GB_PER_CYCLE`.
        That is deliberately distinct from `0`, which is a real override
        meaning this user gets no free traffic at all.
        """
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE users SET lte_free_gb_override = $1 WHERE telegram_id = $2",
            None if gigabytes is None else max(0, int(gigabytes)),
            telegram_id,
        )
        return result != "UPDATE 0"

    async def set_free_gb_override_by_user_id(self, user_id: str, gigabytes: int | None) -> bool:
        """`set_free_gb_override`, addressed by our own id."""
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE users SET lte_free_gb_override = $1 WHERE id = $2::uuid",
            None if gigabytes is None else max(0, int(gigabytes)),
            user_id,
        )
        return result != "UPDATE 0"

    async def set_low_traffic_notified(self, telegram_id: int, threshold_mb: int) -> None:
        """
        Remember which low-traffic warning this user has been sent.

        Set back to 0 when their balance recovers, so a user who tops up and
        later runs low again is warned a second time rather than silently.

        Not clamped to non-negative: `lte_quota.EXHAUSTED` (-1) is a real,
        distinct value here, not an out-of-range one -- see that constant for
        why 0 cannot mean both "recovered" and "empty".
        """
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET lte_low_traffic_notified_mb = $1 WHERE telegram_id = $2",
            int(threshold_mb), telegram_id,
        )

    async def set_blocked(self, telegram_id: int, blocked: bool) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET lte_blocked = $1 WHERE telegram_id = $2", blocked, telegram_id
        )

    async def set_squad_tier(self, telegram_id: int, tier: str) -> None:
        """Record which tier the demotion job last placed this user in."""
        if tier not in ("unknown", "paid", "free"):
            raise ValueError(f"Unknown squad tier: {tier!r}")
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET squad_tier = $1 WHERE telegram_id = $2", tier, telegram_id
        )

    async def set_squad_tier_by_user_id(self, user_id: str, tier: str) -> None:
        """
        Same, addressed by internal id.

        Needed for accounts with no telegram_id -- a website signup. Without
        it their tier stays 'unknown' forever, which the free-squad cleanup
        reads as "not in FREE" and so never removes them.
        """
        if tier not in ("unknown", "paid", "free"):
            raise ValueError(f"Unknown squad tier: {tier!r}")
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET squad_tier = $1 WHERE id = $2::uuid", tier, user_id
        )

    async def set_squad_tiers(self, telegram_ids: list[int], tier: str) -> None:
        """Bulk form of `set_squad_tier`, for a reconciliation sweep."""
        if not telegram_ids:
            return
        if tier not in ("unknown", "paid", "free"):
            raise ValueError(f"Unknown squad tier: {tier!r}")
        pool = await get_pool()
        await pool.execute(
            "UPDATE users SET squad_tier = $1 WHERE telegram_id = ANY($2::bigint[])",
            tier, telegram_ids,
        )

    async def get_tier_counts(self) -> dict[str, int]:
        """How many users sit in each tier, for the admin statistics screen."""
        pool = await get_pool()
        rows = await pool.fetch("SELECT squad_tier, COUNT(*) AS count FROM users GROUP BY squad_tier")
        return {row["squad_tier"]: int(row["count"]) for row in rows}

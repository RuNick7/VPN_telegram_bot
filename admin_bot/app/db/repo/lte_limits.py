"""Persistence for LTE traffic limit balances."""

from __future__ import annotations

from typing import Optional

from app.db.sqlite import db


class LTETrafficLimitsRepository:
    """Repository for LTE traffic counters and paid balance."""

    async def get(self, tg_id: int) -> Optional[dict]:
        row = await db.fetch_one(
            "SELECT * FROM lte_traffic_limits WHERE tg_id = ?",
            (tg_id,),
        )
        return dict(row) if row else None

    async def create_if_missing(self, tg_id: int, cycle_start_ts: int) -> dict:
        await db.execute(
            """
            INSERT OR IGNORE INTO lte_traffic_limits (
                tg_id, cycle_start_ts, paid_balance_bytes, cycle_paid_spent_bytes, is_blocked
            ) VALUES (?, ?, 0, 0, 0)
            """,
            (tg_id, cycle_start_ts),
        )
        await db.commit()
        row = await self.get(tg_id)
        return row or {
            "tg_id": tg_id,
            "cycle_start_ts": cycle_start_ts,
            "paid_balance_bytes": 0,
            "cycle_paid_spent_bytes": 0,
            "is_blocked": 0,
        }

    async def save_state(
        self,
        tg_id: int,
        cycle_start_ts: int,
        paid_balance_bytes: int,
        cycle_paid_spent_bytes: int,
        is_blocked: bool,
        last_total_usage_bytes: int,
        last_remaining_bytes: int,
    ) -> None:
        await db.execute(
            """
            INSERT INTO lte_traffic_limits (
                tg_id, cycle_start_ts, paid_balance_bytes, cycle_paid_spent_bytes, is_blocked,
                last_total_usage_bytes, last_remaining_bytes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tg_id) DO UPDATE SET
                cycle_start_ts = excluded.cycle_start_ts,
                paid_balance_bytes = excluded.paid_balance_bytes,
                cycle_paid_spent_bytes = excluded.cycle_paid_spent_bytes,
                is_blocked = excluded.is_blocked,
                last_total_usage_bytes = excluded.last_total_usage_bytes,
                last_remaining_bytes = excluded.last_remaining_bytes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                tg_id,
                int(cycle_start_ts),
                max(0, int(paid_balance_bytes)),
                max(0, int(cycle_paid_spent_bytes)),
                1 if is_blocked else 0,
                max(0, int(last_total_usage_bytes)),
                max(0, int(last_remaining_bytes)),
            ),
        )
        await db.commit()


lte_limits_repo = LTETrafficLimitsRepository()

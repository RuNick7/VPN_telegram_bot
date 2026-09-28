"""Repository for `bot_events` — replaces the table user_bot/data/event_logger.py
writes to (previously never actually created by _ensure_schema)."""

from __future__ import annotations

from .pool import get_pool


class EventRepository:
    async def log_event(self, telegram_id: int, callback_data: str | None, step: str | None) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO bot_events (telegram_id, callback_data, step, ts)
            VALUES ($1, $2, $3, now())
            """,
            telegram_id, callback_data or "", step or "",
        )

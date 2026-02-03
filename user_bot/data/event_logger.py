# middlewares/event_logger.py
from __future__ import annotations

import logging, pathlib, os, asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable

from pathlib import Path
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Update, TelegramObject
from data.db_utils import get_db

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH_ENV = os.getenv("DB_PATH")
DB_PATH = Path(DB_PATH_ENV) if DB_PATH_ENV else DATA_DIR / "subscription.db"

class EventLogger(BaseMiddleware):
    """
    Логирует нажатия inline-кнопок (CallbackQuery) в SQLite.
    """

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)

    # ── подключаемся при старте бота ────────────────────────────────────────
    async def startup(self) -> None:
        self.log.info("EventLogger: ready for %s", DB_PATH.resolve())

    async def shutdown(self) -> None:
        self.log.info("EventLogger: stopped")

    # ── главный вызов middleware ────────────────────────────────────────────
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:

        # 1) пытаемся извлечь CallbackQuery
        cb: CallbackQuery | None = None

        if isinstance(event, CallbackQuery):
            cb = event                                 # уже сам CallbackQuery
        elif isinstance(event, Update) and event.callback_query:
            cb = event.callback_query                  # Update → его часть

        # 2) если найдено — сохраняем
        if cb:
            try:
                await self._save_cb(cb)
            except Exception as exc:
                self.log.exception("EventLogger write failed: %s", exc)

        # 3) передаём управление дальше
        return await handler(event, data)

    # ── приватный метод записи в таблицу ────────────────────────────────────
    def _save_cb_sync(self, cb: CallbackQuery) -> None:
        step = cb.data.split(":", 1)[0] if cb.data else None
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO bot_events (user_id, callback_data, step, ts)
                VALUES (?, ?, ?, ?)
                """,
                (cb.from_user.id, cb.data, step, datetime.utcnow()),
            )
            conn.commit()

    async def _save_cb(self, cb: CallbackQuery) -> None:
        await asyncio.to_thread(self._save_cb_sync, cb)

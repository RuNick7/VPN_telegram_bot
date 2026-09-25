# middlewares/event_logger.py
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Update, TelegramObject
from tgvpn_shared.db import EventRepository

_events = EventRepository()


class EventLogger(BaseMiddleware):
    """
    Логирует нажатия inline-кнопок (CallbackQuery) в Postgres.
    """

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)

    # ── подключаемся при старте бота ────────────────────────────────────────
    async def startup(self) -> None:
        self.log.info("EventLogger: ready")

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

    # ── запись события ──────────────────────────────────────────────────────
    async def _save_cb(self, cb: CallbackQuery) -> None:
        step = cb.data.split(":", 1)[0] if cb.data else None
        await _events.log_event(cb.from_user.id, cb.data, step)

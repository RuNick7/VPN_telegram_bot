"""
Router-level admin authorization.

Every admin handler used to open with its own `check_admin_access` call -- ~70
of them across five modules, each with slightly different rejection wording and
state-clearing behaviour. Authorization by per-handler discipline means one
forgotten call is an unauthenticated admin action, and nothing in the code
makes that visible.

Attaching this to the admin router makes it structural instead: a handler
cannot be reached without passing the check, whether or not its author
remembered to write one.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.access import check_admin_access

logger = logging.getLogger(__name__)

DENIED_TEXT = "❌ Доступ запрещен."


class AdminAccessMiddleware(BaseMiddleware):
    """Reject non-admin updates before any admin handler runs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            # No identifiable sender (channel post, service message): nothing to
            # authorize, so there is nothing to let through either.
            return None

        if await check_admin_access(user.id):
            return await handler(event, data)

        logger.warning("Denied admin access to %s", user.id)

        # Clear any half-finished FSM flow so the next authorized user doesn't
        # inherit a stranger's partially filled form.
        state = data.get("state")
        if state is not None:
            await state.clear()

        if isinstance(event, CallbackQuery):
            await event.answer(DENIED_TEXT, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(DENIED_TEXT)
        return None

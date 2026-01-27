"""Error reporting middleware and handler for exceptions."""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.dispatcher.flags import get_flag
import logging

from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)


class ErrorReporterMiddleware(BaseMiddleware):
    """Middleware to catch exceptions and report them to admins."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception("Unhandled exception in handler")
            try:
                await send_admin_message(f"❌ Ошибка в боте:\n\n{type(e).__name__}: {str(e)}")
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
            raise

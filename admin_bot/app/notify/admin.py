"""Admin notification functions."""

import asyncio
import html
import logging
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile

from app.config.settings import settings


logger = logging.getLogger(__name__)


def _is_transient_send_error(exc: Exception) -> bool:
    """
    Return True for temporary Telegram/network failures worth retrying.
    """
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "bad gateway",
            "gateway timeout",
            "timeout",
            "temporarily unavailable",
            "server disconnected",
            "connection reset",
            "network",
        )
    )


async def _send_with_retry(coro_factory, *, attempts: int = 3, base_delay: float = 0.7) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await coro_factory()
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= attempts or not _is_transient_send_error(exc):
                raise
            await asyncio.sleep(base_delay * attempt)
    if last_exc:
        raise last_exc


async def send_admin_message(text: str, bot: Optional[Bot] = None) -> None:
    """Send a message to all admin users."""
    created_bot = bot is None
    if not bot:
        from app.bot.factory import create_bot
        bot = create_bot()

    safe_text = html.escape(text)
    max_chunk = 4000
    chunks = [safe_text[i:i + max_chunk] for i in range(0, len(safe_text), max_chunk)] or [""]

    for admin_id in settings.admin_ids:
        try:
            for chunk in chunks:
                await _send_with_retry(
                    lambda: bot.send_message(chat_id=admin_id, text=f"<pre>{chunk}</pre>")
                )
        except Exception as e:
            # Log error but don't raise to avoid recursion
            logger.error(f"Failed to send admin message to {admin_id}: {e}")
    if created_bot:
        await bot.session.close()


async def send_log_file(bot: Optional[Bot] = None) -> None:
    """Send log file to all admin users."""
    created_bot = bot is None
    if not bot:
        from app.bot.factory import create_bot
        bot = create_bot()

    log_path = Path(settings.log_file)
    if not log_path.exists():
        return

    log_file = FSInputFile(log_path)

    for admin_id in settings.admin_ids:
        try:
            await _send_with_retry(
                lambda: bot.send_document(chat_id=admin_id, document=log_file)
            )
        except Exception as e:
            logger.error(f"Failed to send log file to {admin_id}: {e}")
    if created_bot:
        await bot.session.close()

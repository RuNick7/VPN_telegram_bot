"""Admin notification functions."""

import asyncio
import html
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile

from app.config.settings import settings


async def send_admin_message(text: str, bot: Optional[Bot] = None) -> None:
    """Send a message to all admin users."""
    created_bot = bot is None
    if not bot:
        from app.bot.factory import create_bot
        bot = create_bot()

    for admin_id in settings.admin_ids:
        try:
            safe_text = html.escape(text)
            await bot.send_message(chat_id=admin_id, text=f"<pre>{safe_text}</pre>")
        except Exception as e:
            # Log error but don't raise to avoid recursion
            import logging
            logger = logging.getLogger(__name__)
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
            await bot.send_document(chat_id=admin_id, document=log_file)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send log file to {admin_id}: {e}")
    if created_bot:
        await bot.session.close()

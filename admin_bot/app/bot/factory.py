"""Bot and dispatcher factory with dependency injection setup."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config.settings import settings


def create_bot() -> Bot:
    """Create and configure Bot instance."""
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


def create_dp() -> Dispatcher:
    """Create and configure Dispatcher instance."""
    dp = Dispatcher()
    # Wiring and router setup will be done here
    return dp

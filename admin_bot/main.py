
"""Bot entrypoint."""

import asyncio
import logging

from app.bot.factory import create_bot, create_dp
from app.bot.routers import get_all_routers
from app.notify.log_setup import setup_logging
from app.scheduler.setup import create_scheduler


async def main() -> None:
    """Run the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    bot = create_bot()
    dp = create_dp()

    for router in get_all_routers():
        dp.include_router(router)

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")

    logger.info("Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

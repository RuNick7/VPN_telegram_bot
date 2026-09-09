
"""Bot entrypoint."""

import asyncio
import logging

from app.bot.factory import create_bot, create_dp
from app.bot.routers import get_all_routers
from app.config.settings import settings
from app.notify.log_setup import setup_logging
from app.scheduler.jobs.subscription_expire_monitor import run_catchup_sweep
from app.scheduler.setup import create_scheduler
from app.services.users import user_service
from tgvpn_shared.db import close_pool


async def main() -> None:
    """Run the bot."""
    # Fail before touching Telegram or Postgres if the process is misconfigured.
    settings.require("admin_bot_token", "database_url", "remnawave_base_url")

    setup_logging()
    logger = logging.getLogger(__name__)

    bot = create_bot()
    dp = create_dp()

    for router in get_all_routers():
        dp.include_router(router)

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")

    # Reconcile before the first scheduled tick: anyone whose subscription
    # lapsed while this process was down is still on a paid squad right now,
    # and waiting out the interval would extend that. Detached so a slow or
    # failing sweep can't hold up polling.
    asyncio.create_task(run_catchup_sweep())

    logger.info("Bot started.")
    try:
        await dp.start_polling(bot)
    finally:
        await user_service.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

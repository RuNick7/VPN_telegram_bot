# main.py
# ──────────────────────────────────────────────────────────────────────
import asyncio, logging

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramForbiddenError
from tgvpn_shared.settings import get_settings
from app.services.remnawave.vpn_service import close_client as close_remnawave_client
from data.event_logger import EventLogger           # ← NEW
from precache_videos import precache_videos, _load_cache
from utils.heartbeat import heartbeat_loop
from utils.reminders import reminders_scheduler
from handlers.user_handlers import router as user_router
from middlewares.email_gate import EmailGateMiddleware

# ── config ────────────────────────────────────────────────────────────
settings = get_settings()
settings.require("user_bot_token", "database_url", "remnawave_base_url")
ADMIN_ID = settings.primary_admin_id

bot = Bot(token=settings.user_bot_token)
dp  = Dispatcher()
VIDEO_ID_CACHE: dict = {}
reminders_task: asyncio.Task | None = None
heartbeat_task: asyncio.Task | None = None

# ─── MIDDLEWARE: сбор кликов ─────────────────────────────────────────
evlog = EventLogger()          # экземпляр; соединится при startup
dp.update.middleware(evlog)    # регистрируем в диспетчере
dp.message.middleware(EmailGateMiddleware())

# ─── STARTUP HOOK ────────────────────────────────────────────────────
async def on_startup(dispatcher: Dispatcher) -> None:
    global reminders_task
    global VIDEO_ID_CACHE
    if ADMIN_ID:
        try:
            VIDEO_ID_CACHE = await precache_videos(bot, ADMIN_ID)
            print("Video cache ready:", VIDEO_ID_CACHE)
        except asyncio.CancelledError:
            logging.info("Startup cancelled during video precache.")
            raise
        except Exception:
            logging.exception("Video precache failed; continue without blocking startup.")
    else:
        logging.warning("ADMIN_ID not set; skipping video precache")

    global heartbeat_task
    # Liveness signal for admin_bot's health monitor: a wedged event loop
    # stops touching the file, which is otherwise indistinguishable from a
    # healthy idle bot.
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    reminders_task = asyncio.create_task(reminders_scheduler(bot))   # фоновый планировщик

    def _reminders_done(task: asyncio.Task) -> None:
        if task.cancelled():
            logging.info("reminders_scheduler cancelled.")
            return
        exc = task.exception()
        if exc:
            logging.error("reminders_scheduler stopped: %s", exc)

    reminders_task.add_done_callback(_reminders_done)
    # открываем SQLite для middleware
    await evlog.startup()

# ─── SHUTDOWN HOOK ───────────────────────────────────────────────────
async def on_shutdown(dispatcher: Dispatcher) -> None:
    global reminders_task, heartbeat_task
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
    if reminders_task and not reminders_task.done():
        reminders_task.cancel()
        try:
            await reminders_task
        except asyncio.CancelledError:
            pass
    await evlog.shutdown()
    await close_remnawave_client()


@dp.error()
async def ignored_blocked_users(event: ErrorEvent) -> bool:
    if isinstance(event.exception, TelegramForbiddenError):
        logging.warning("Telegram user blocked bot; skipping update: %s", event.exception)
        return True
    return False

# ─── MAIN ────────────────────────────────────────────────────────────
def main() -> None:
    # DEBUG нельзя в проде: aiogram на этом уровне пишет полные апдейты
    # (сообщения и данные пользователей) в лог.
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("🚀 Запуск бота...")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.include_router(user_router)

    dp.run_polling(bot)            # Dispatcher сам запускает цикл событий

if __name__ == "__main__":
    main()


# main.py
# ──────────────────────────────────────────────────────────────────────
import os, asyncio, logging, pathlib
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from data.event_logger import EventLogger           # ← NEW
from precache_videos import precache_videos, _load_cache
from utils.reminders import reminders_scheduler
from handlers.user_handlers import router as user_router
from middlewares.email_gate import EmailGateMiddleware

# ── .env ──────────────────────────────────────────────────────────────
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")
USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN")
admin_ids_raw = os.getenv("ADMIN_IDS") or ""
ADMIN_ID = int(admin_ids_raw.split(",")[0].strip() or "0")

bot = Bot(token=USER_BOT_TOKEN)
dp  = Dispatcher()
VIDEO_ID_CACHE: dict = {}

# ─── MIDDLEWARE: сбор кликов ─────────────────────────────────────────
evlog = EventLogger()          # экземпляр; соединится при startup
dp.update.middleware(evlog)    # регистрируем в диспетчере
dp.message.middleware(EmailGateMiddleware())

# ─── STARTUP HOOK ────────────────────────────────────────────────────
async def on_startup(dispatcher: Dispatcher) -> None:
    global VIDEO_ID_CACHE
    if ADMIN_ID:
        VIDEO_ID_CACHE = await precache_videos(bot, ADMIN_ID)
        print("Video cache ready:", VIDEO_ID_CACHE)
    else:
        logging.warning("ADMIN_ID not set; skipping video precache")

    reminders_task = asyncio.create_task(reminders_scheduler(bot))   # фоновый планировщик
    reminders_task.add_done_callback(
        lambda task: logging.error("reminders_scheduler stopped: %s", task.exception())
        if task.exception() else None
    )
    # открываем SQLite для middleware
    await evlog.startup()

# ─── SHUTDOWN HOOK ───────────────────────────────────────────────────
async def on_shutdown(dispatcher: Dispatcher) -> None:
    await evlog.shutdown()

# ─── MAIN ────────────────────────────────────────────────────────────
def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
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


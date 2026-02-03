# precache_videos.py  (или тот файл, где лежит логика кэширования)
import json, logging
from pathlib import Path
from typing import Dict

from aiogram import Bot
from aiogram.types import FSInputFile


# ── 1. Фиксируем «якорь» — папка user_bot ───────────────────────
BASE_DIR  = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "video"

# ── 2. Карта роликов с абсолютными путями ───────────────────────
VIDEOS: Dict[str, Path] = {
    "android": VIDEO_DIR / "Android.mp4",
    "ios":     VIDEO_DIR / "ios.mp4",
    "windows": VIDEO_DIR / "windows.mp4",
    "macos":   VIDEO_DIR / "MacOS.mp4",
}

# ── 3. Кэш тоже в абсолютном виде ───────────────────────────────
CACHE_FILE = VIDEO_DIR / "cache.json"        # <-- главное исправление

# ── 4. Вспомогательные функции кэша ─────────────────────────────
def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}

def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

# ── 5. Главная процедура — безопасна, не роняет бота ────────────
async def precache_videos(bot: Bot, admin_chat_id: int) -> dict:
    """
    Загружает локальные MP4 в чат admin_chat_id, сохраняет их file_id.
    Возвращает словарь {alias: file_id}.
    """
    if not admin_chat_id:
        logging.info("⚠️ precache_videos skipped: ADMIN_ID is not set")
        return {}
    cache   = _load_cache()
    updated = False

    # precache_videos.py  (перед bot.send_video)

    for alias, path in VIDEOS.items():
        logging.info("📼 %s: %s  exists=%s  size=%.1f MB",
                     alias, path, path.exists(),
                     path.stat().st_size / 1048576 if path.exists() else -1)

        if alias in cache or not path.exists():
            continue

        try:
            # ТОЧНО так же открываем файл, как сделает aiohttp
            with path.open("rb") as test_fh:
                test_fh.read(1)
            logging.info("✅ os.open OK, отправляю…")
        except Exception as e:
            logging.exception("❌ Не открывается локально: %s", e)
            continue

        try:
            msg = await bot.send_video(
                admin_chat_id,
                FSInputFile(str(path)),  # ← строка, не Path
                supports_streaming=True,
                disable_notification=True,
                caption=f"[precache] {alias}",
            )
            cache[alias] = msg.video.file_id
            updated = True
        except Exception as e:
            logging.exception("⚠️ send_video(%s) failed: %s", alias, e)

    if updated:
        _save_cache(cache)

    return cache

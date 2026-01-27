"""Daily subscription DB backup and admin delivery."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from aiogram.types import FSInputFile

from app.bot.factory import create_bot
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _backup_sqlite_db(source_path: Path, dest_path: Path) -> None:
    """Create a safe SQLite backup using SQLite backup API."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as src, sqlite3.connect(dest_path) as dst:
        src.backup(dst)


def _cleanup_old_backups(backup_dir: Path, keep_last: int = 10) -> None:
    """Remove old backup files, keep only the newest N."""
    if not backup_dir.exists():
        return
    backups = sorted(
        [p for p in backup_dir.glob("subscription_*.db") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep_last:]:
        try:
            old.unlink()
        except Exception as e:
            logger.warning("Failed to delete old backup %s: %s", old, e)


async def run_subscription_db_backup() -> None:
    """Backup subscription DB and send to admins."""
    try:
        source_path = Path(settings.user_bot_db_path)
        if not source_path.exists():
            logger.warning("Subscription DB not found: %s", source_path)
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = Path(settings.subscription_db_backup_dir)
        dest_path = dest_dir / f"subscription_{timestamp}.db"

        _backup_sqlite_db(source_path, dest_path)
        _cleanup_old_backups(dest_dir, keep_last=10)

        bot = create_bot()
        try:
            doc = FSInputFile(dest_path)
            for admin_id in settings.admin_ids:
                await bot.send_document(
                    chat_id=admin_id,
                    document=doc,
                    caption=f"📦 Бэкап subscription.db ({timestamp})"
                )
        finally:
            await bot.session.close()
    except Exception as e:
        logger.error("Subscription DB backup failed: %s", e, exc_info=True)

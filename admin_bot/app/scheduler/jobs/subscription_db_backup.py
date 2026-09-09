"""
Daily database backup, delivered to admins over Telegram.

Until Phase 2 this copied the SQLite file through sqlite3's backup API and ran
that blocking copy directly on the event loop. There is no SQLite file any
more, so it now shells out to `pg_dump` -- in a thread, since that call blocks
too.

This is a convenience backup, not a backup strategy: it exists so an admin has
a recent dump in their chat. Real disaster recovery should be infrastructure
level (volume snapshots or a scheduled `pg_dump` to off-host storage).
"""

import asyncio
import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from aiogram.types import FSInputFile

from app.bot.factory import create_bot
from app.config.settings import settings

logger = logging.getLogger(__name__)

KEEP_LAST_BACKUPS = 10
PG_DUMP_TIMEOUT_SECONDS = 300
# Telegram rejects documents above 50 MB from bots.
TELEGRAM_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _scrub(text: str, database_url: str) -> str:
    """Replace the connection string and its password wherever they appear."""
    cleaned = text.replace(database_url, "<database_url>")
    password = urlsplit(database_url).password
    if password:
        cleaned = cleaned.replace(password, "<password>")
    return cleaned


def pg_env(database_url: str) -> dict[str, str]:
    """
    A connection string as the individual PG* variables libpq reads.

    Not `PGDATABASE=<the whole URL>`: that variable is the database *name* and
    is never expanded as a URI, so libpq took `postgresql://...` for a database
    called that, found no host, and fell back to a local socket that does not
    exist in this container. The password still stays out of argv -- which is
    the point of doing this at all, since a process's arguments are readable by
    every local user -- but each part now goes to the variable that means it.
    """
    parts = urlsplit(database_url)
    env: dict[str, str] = {}

    if parts.hostname:
        env["PGHOST"] = parts.hostname
    if parts.port:
        env["PGPORT"] = str(parts.port)
    # Percent-decoded: a password with an `@` or a `/` in it has to be encoded
    # in the URL and must not reach libpq still encoded.
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)

    name = parts.path.lstrip("/")
    if name:
        env["PGDATABASE"] = unquote(name)

    sslmode = parse_qs(parts.query).get("sslmode")
    if sslmode and sslmode[0]:
        env["PGSSLMODE"] = sslmode[0]
    return env


def _dump_database(database_url: str, dest_path: Path) -> None:
    """Write a gzipped `pg_dump` of the database to `dest_path`."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-privileges"],
        capture_output=True,
        timeout=PG_DUMP_TIMEOUT_SECONDS,
        env={**os.environ, **pg_env(database_url)},
    )
    if result.returncode != 0:
        # Truncated and scrubbed: pg_dump echoes the connection string it was
        # given in some failure modes, and this text goes into a log file that
        # is itself sent to admins over Telegram.
        detail = result.stderr.decode(errors="replace")[:500]
        raise RuntimeError(f"pg_dump exited {result.returncode}: {_scrub(detail, database_url)}")
    with gzip.open(dest_path, "wb") as handle:
        handle.write(result.stdout)


def _cleanup_old_backups(backup_dir: Path, keep_last: int) -> None:
    """Delete all but the newest `keep_last` dumps."""
    if not backup_dir.exists():
        return
    dumps = sorted(
        (p for p in backup_dir.glob("tgvpn_*.sql.gz") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in dumps[keep_last:]:
        try:
            old.unlink()
        except Exception as exc:
            logger.warning("Failed to delete old backup %s: %s", old, exc)


async def run_subscription_db_backup() -> None:
    """Dump the database and send it to every configured admin."""
    try:
        if not settings.database_url:
            logger.warning("DATABASE_URL is not set; skipping database backup.")
            return
        if shutil.which("pg_dump") is None:
            logger.warning("pg_dump not found on PATH; skipping database backup.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = Path(settings.subscription_db_backup_dir)
        dest_path = dest_dir / f"tgvpn_{timestamp}.sql.gz"

        await asyncio.to_thread(_dump_database, settings.database_url, dest_path)
        _cleanup_old_backups(dest_dir, KEEP_LAST_BACKUPS)

        size = dest_path.stat().st_size
        if size > TELEGRAM_MAX_UPLOAD_BYTES:
            logger.warning(
                "Backup %s is %.1f MB, too large for Telegram; kept on disk only.",
                dest_path,
                size / 1024 / 1024,
            )
            return

        bot = create_bot()
        try:
            document = FSInputFile(dest_path)
            for admin_id in settings.admin_ids:
                await bot.send_document(
                    chat_id=admin_id,
                    document=document,
                    caption=f"📦 Бэкап базы данных ({timestamp})",
                )
        finally:
            await bot.session.close()
    except Exception as exc:
        logger.error("Database backup failed: %s", exc, exc_info=True)

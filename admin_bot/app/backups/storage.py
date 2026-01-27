"""Backup storage management: rotation, file naming, cleanup."""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


def get_backup_dir() -> Path:
    """Get backup directory path."""
    return Path(settings.backup_dir)


def generate_backup_filename(prefix: str = "backup") -> str:
    """Generate backup filename with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.backup"


def list_backups(prefix: Optional[str] = None) -> List[Path]:
    """List all backup files, optionally filtered by prefix."""
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return []

    pattern = f"{prefix}_*.backup" if prefix else "*.backup"
    backups = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


def rotate_backups(retention_days: Optional[int] = None) -> int:
    """
    Remove old backup files based on retention policy.

    Returns:
        Number of files deleted.
    """
    retention_days = retention_days or settings.backup_retention_days
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_timestamp = cutoff_date.timestamp()

    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return 0

    deleted_count = 0
    for backup_file in backup_dir.glob("*.backup"):
        if backup_file.stat().st_mtime < cutoff_timestamp:
            try:
                backup_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old backup: {backup_file.name}")
            except Exception as e:
                logger.error(f"Failed to delete backup {backup_file.name}: {e}")

    if deleted_count > 0:
        logger.info(f"Rotated {deleted_count} old backup(s)")

    return deleted_count

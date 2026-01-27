"""Backup service layer."""

import logging
from typing import Optional
from app.backups import remnawave_db, storage

logger = logging.getLogger(__name__)


class BackupService:
    """Service for backup operations."""

    async def create_backup(self) -> str:
        """Create a new backup and return its path."""
        backup_path = await remnawave_db.backup_remnawave_db()
        return str(backup_path)

    async def list_backups(self, prefix: Optional[str] = None) -> list[str]:
        """List all backup files."""
        backups = storage.list_backups(prefix=prefix)
        return [str(b) for b in backups]

    async def rotate_backups(self, retention_days: Optional[int] = None) -> int:
        """Rotate old backups."""
        return storage.rotate_backups(retention_days=retention_days)


backup_service = BackupService()

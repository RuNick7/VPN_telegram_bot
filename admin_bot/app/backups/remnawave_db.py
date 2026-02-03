"""Remnawave database backup logic."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.api.client import RemnawaveClient
from app.config.settings import settings

logger = logging.getLogger(__name__)


async def backup_remnawave_db(backup_dir: Optional[str] = None) -> Path:
    """
    Backup Remnawave database via API.

    Returns:
        Path to the created backup file.
    """
    backup_dir_path = Path(backup_dir or settings.backup_dir)
    backup_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"remnawave_db_{timestamp}.backup"
    backup_path = backup_dir_path / backup_filename

    client = RemnawaveClient()
    try:
        # Fetch database export from API
        # Adjust endpoint based on actual Remnawave API
        db_data = await client.get("/v1/database/export")

        # Save backup file
        # Assuming API returns JSON or binary data
        if isinstance(db_data, dict):
            import json
            backup_path.write_text(json.dumps(db_data, indent=2), encoding="utf-8")
        else:
            backup_path.write_bytes(db_data)

        logger.info(f"Remnawave DB backup created: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Failed to create Remnawave DB backup: {e}", exc_info=True)
        raise
    finally:
        await client.close()

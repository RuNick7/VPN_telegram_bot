"""Daily backup job."""

import logging
from app.services.backups import backup_service

logger = logging.getLogger(__name__)


async def run_backup() -> None:
    """Execute daily backup task."""
    try:
        logger.info("Starting daily backup job...")
        await backup_service.create_backup()
        logger.info("Daily backup job completed successfully")
    except Exception as e:
        logger.error(f"Daily backup job failed: {e}", exc_info=True)

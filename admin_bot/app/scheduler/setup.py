"""APScheduler setup and configuration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs import daily_backup, node_monitor, subscription_db_backup, inactive_user_cleanup
from app.config.settings import settings


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler with jobs."""
    scheduler = AsyncIOScheduler()

    # Add daily backup job (runs at 3:00 AM every day)
    scheduler.add_job(
        daily_backup.run_backup,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_backup",
        name="Daily Remnawave DB Backup",
        replace_existing=True
    )

    scheduler.add_job(
        subscription_db_backup.run_subscription_db_backup,
        trigger=CronTrigger(hour=17, minute=0, timezone="Europe/Moscow"),
        id="subscription_db_backup",
        name="Daily Subscription DB Backup",
        replace_existing=True
    )

    scheduler.add_job(
        node_monitor.run_node_monitor,
        trigger="interval",
        minutes=settings.monitor_interval_minutes,
        id="node_monitor",
        name="Node and Squad Monitor",
        replace_existing=True
    )

    scheduler.add_job(
        inactive_user_cleanup.run_inactive_user_cleanup,
        trigger=CronTrigger(hour=4, minute=30, timezone="Europe/Moscow"),
        id="inactive_user_cleanup",
        name="Inactive Remnawave User Cleanup",
        replace_existing=True,
    )

    return scheduler

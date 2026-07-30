"""APScheduler setup and configuration."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.settings import settings
from app.scheduler.jobs import (
    inactive_user_cleanup,
    lte_traffic_monitor,
    node_monitor,
    service_health_monitor,
    subscription_db_backup,
    subscription_expire_monitor,
)

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler with jobs."""
    scheduler = AsyncIOScheduler()

    # There is no "Daily Remnawave DB Backup" job any more: it called
    # /v1/database/export, which this panel does not expose (every candidate
    # backup endpoint returns 404), so it failed every night and never once
    # produced a backup. Remnawave's own backup facility is the place for
    # panel-side dumps; `subscription_db_backup` below covers *our* database.

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

    # With the FREE tier on, panel accounts no longer expire by themselves --
    # this job is what actually enforces expiry, so it runs frequently and is
    # watched by the health monitor below.
    if settings.free_tier_enabled:
        scheduler.add_job(
            subscription_expire_monitor.run_subscription_expire_monitor,
            trigger="interval",
            minutes=settings.monitor_interval_minutes,
            id=subscription_expire_monitor.JOB_NAME,
            name="Subscription Expiry / FREE Squad Monitor",
            replace_existing=True,
        )
    else:
        logger.info("FREE tier is disabled (FREE_TIER_ENABLED=false); expiry monitor not scheduled")

    if settings.lte_enabled:
        scheduler.add_job(
            lte_traffic_monitor.run_lte_traffic_monitor,
            trigger="interval",
            minutes=settings.monitor_interval_minutes,
            id=lte_traffic_monitor.JOB_NAME,
            name="LTE Traffic Quota Monitor",
            replace_existing=True,
        )
    else:
        logger.info("LTE quotas are disabled (LTE_ENABLED=false); traffic monitor not scheduled")

    if settings.service_monitor_enabled:
        scheduler.add_job(
            service_health_monitor.run_service_health_monitor,
            trigger="interval",
            minutes=settings.monitor_interval_minutes,
            id="service_health_monitor",
            name="Service Health Monitor",
            replace_existing=True,
        )

    return scheduler

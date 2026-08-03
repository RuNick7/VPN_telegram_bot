"""
Notice when something has quietly stopped working.

Ported from the never-merged branch `claude/fervent-napier-fe366c` and extended
with the check this phase actually needs: **has the demotion job succeeded
recently?**

That check is the reason the FREE tier is safe to run at all. With the FREE
tier on, panel accounts no longer expire on their own, so
`subscription_expire_monitor` is the only thing separating a lapsed
subscription from continued paid access. A crashed scheduler, an unhandled
exception every tick, a job that was never registered -- all of them look
identical from the outside: nothing happens, and nothing complains. Staleness
is judged on last *success*, so a job failing every five minutes still alerts.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import aiohttp
from aiogram import Bot
from tgvpn_shared.db import JobRunRepository

from app.config.settings import settings
from app.notify.admin import send_admin_message
from app.scheduler.jobs import lte_traffic_monitor, subscription_expire_monitor

logger = logging.getLogger(__name__)

# Repeat alerts at most this often. Long enough not to spam a chat during an
# outage, short enough that a still-broken system keeps reminding you.
ALERT_THROTTLE_SECONDS = 600
WEBHOOK_TIMEOUT_SECONDS = 5

_last_alert_ts: float | None = None

# When this process came up.
#
# A job that has never succeeded is normally a real fault -- it was never
# registered, or it throws on every tick. Right after a start it means
# something else entirely: the job simply has not had its first tick yet.
# Both monitors run on the same interval, so whichever fires first sees an
# empty `job_runs` and reports the other as dead. That is what happened the
# moment LTE_ENABLED was switched on: an alert for a job that ran fine four
# minutes later.
_started_at = time.time()


def _stale_after_seconds() -> int:
    """
    How long without a success before a job counts as dead.

    A multiple of the job's own interval, so one missed tick reads as
    scheduling jitter and two in a row do not.
    """
    interval = max(1, settings.monitor_interval_minutes) * 60
    return int(interval * max(1.0, settings.job_stale_interval_multiplier))


def format_stale_job(job_name: str, state: dict, threshold_seconds: int) -> str:
    """Describe a stale job, including what it means for users."""
    last_success = state.get("last_success_at")
    if last_success:
        age_minutes = (time.time() - int(last_success)) / 60
        when = f"последний успешный проход {age_minutes:.0f} мин назад"
    else:
        when = "ни одного успешного прохода"

    detail = f"задача «{job_name}»: {when} (порог {threshold_seconds // 60} мин)"
    failures = int(state.get("consecutive_failures") or 0)
    if failures:
        detail += f", подряд ошибок: {failures}"
    if state.get("last_error"):
        detail += f"\n  причина: {str(state['last_error'])[:200]}"
    return detail


async def _check_webhook() -> str | None:
    try:
        timeout = aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(settings.webhook_health_url) as response:
                if response.status != 200:
                    return f"webhook /health вернул HTTP {response.status}"
    except Exception as exc:
        return f"webhook недоступен: {exc}"
    return None


def _check_heartbeat() -> str | None:
    """
    A stale heartbeat file means user_bot's event loop is wedged.

    Worth checking separately from "is the process alive": a blocked loop keeps
    the process running and the container healthy while serving nobody.
    """
    path = Path(settings.user_bot_heartbeat_path)
    if not path.exists():
        return f"heartbeat-файл user_bot не найден: {path}"

    age_seconds = time.time() - path.stat().st_mtime
    threshold = settings.service_monitor_stale_minutes * 60
    if age_seconds > threshold:
        return (
            f"heartbeat user_bot устарел на {age_seconds / 60:.1f} мин "
            f"(порог {settings.service_monitor_stale_minutes} мин) — event loop мог зависнуть"
        )
    return None


async def _check_telegram() -> str | None:
    if not settings.user_bot_token:
        return None
    bot = Bot(token=settings.user_bot_token.strip())
    try:
        await bot.get_me()
    except Exception as exc:
        return f"user_bot getMe провалился: {exc}"
    finally:
        await bot.session.close()
    return None


async def _check_jobs(jobs: JobRunRepository) -> list[str]:
    """
    Flag enforcement jobs that have stopped succeeding.

    Only jobs whose feature is switched on are checked -- a disabled job never
    running is correct, not a fault.
    """
    threshold = _stale_after_seconds()
    watched = []
    if settings.free_tier_enabled:
        watched.append(subscription_expire_monitor.JOB_NAME)
    if settings.lte_enabled:
        watched.append(lte_traffic_monitor.JOB_NAME)

    # A job that has never run gets until the threshold to have its first tick.
    # Beyond that, silence really is a fault -- but complaining inside that
    # window turns every deploy that enables a feature into a false alarm.
    young = (time.time() - _started_at) < threshold

    issues = []
    for job_name in watched:
        state = await jobs.find_stale(job_name, threshold)
        if state is None:
            continue
        if young and not state.get("last_attempt_at"):
            logger.info(
                "%s has not run yet and this process is %.0fs old; not alerting",
                job_name, time.time() - _started_at,
            )
            continue
        issues.append(format_stale_job(job_name, state, threshold))
    return issues


async def run_service_health_monitor() -> None:
    """Check every liveness signal and alert on anything broken."""
    if not settings.service_monitor_enabled:
        return

    issues: list[str] = []
    for check in (await _check_webhook(), _check_heartbeat(), await _check_telegram()):
        if check:
            issues.append(check)

    try:
        issues.extend(await _check_jobs(JobRunRepository()))
    except Exception as exc:
        # A database that can't answer is itself worth reporting -- the
        # enforcement jobs read the same database.
        issues.append(f"не удалось проверить состояние задач: {exc}")

    if not issues:
        logger.debug("Service health monitor: all systems OK")
        return

    global _last_alert_ts
    now = time.time()
    if _last_alert_ts is not None and now - _last_alert_ts < ALERT_THROTTLE_SECONDS:
        logger.info("Service health alerts throttled (%d issues)", len(issues))
        return

    await send_admin_message(
        "🚨 Мониторинг сервисов — обнаружены проблемы:\n"
        + "\n".join(f"• {issue}" for issue in issues)
    )
    _last_alert_ts = now

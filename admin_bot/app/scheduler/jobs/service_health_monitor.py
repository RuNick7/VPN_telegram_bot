"""Health-check monitor for KairaVPN services.

Runs every monitor_interval_minutes and reports to admins if:
  - YooKassa webhook is unreachable
  - user_bot heartbeat file is stale (event loop may be stuck)
  - user_bot Telegram connection fails (getMe)
"""

import logging
import time
from pathlib import Path

import aiohttp
from aiogram import Bot

from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)

ALERT_THROTTLE_SECONDS = 600
_last_alert_ts: float | None = None


async def run_service_health_monitor() -> None:
    """Check webhook liveness and user_bot heartbeat, notify on issues."""
    if not settings.service_monitor_enabled:
        return

    issues: list[str] = []

    # 1. Ping YooKassa webhook /health
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(settings.webhook_health_url) as resp:
                if resp.status != 200:
                    issues.append(f"webhook /health вернул HTTP {resp.status}")
    except Exception as exc:
        issues.append(f"webhook недоступен: {exc}")

    # 2. Check user_bot heartbeat file freshness
    hb_path = Path(settings.user_bot_heartbeat_path)
    if hb_path.exists():
        age_seconds = time.time() - hb_path.stat().st_mtime
        stale_threshold = settings.service_monitor_stale_minutes * 60
        if age_seconds > stale_threshold:
            issues.append(
                f"user_bot heartbeat устарел на {age_seconds / 60:.1f} мин "
                f"(порог {settings.service_monitor_stale_minutes} мин) — "
                f"event loop мог зависнуть"
            )
    else:
        issues.append(
            f"user_bot heartbeat файл не найден: {hb_path} — "
            f"user_bot не запущен или не записал heartbeat"
        )

    # 3. Verify user_bot Telegram connection via getMe
    if settings.user_bot_token:
        try:
            user_bot = Bot(token=settings.user_bot_token.strip())
            await user_bot.get_me()
            await user_bot.session.close()
        except Exception as exc:
            issues.append(f"user_bot getMe провалился: {exc}")

    if not issues:
        logger.debug("Service health monitor: all systems OK")
        return

    global _last_alert_ts
    now = time.time()
    if _last_alert_ts is not None and now - _last_alert_ts < ALERT_THROTTLE_SECONDS:
        logger.info("Service health alerts throttled (%d issues)", len(issues))
        return

    text = "🚨 Мониторинг сервисов — обнаружены проблемы:\n" + "\n".join(
        f"• {issue}" for issue in issues
    )
    await send_admin_message(text)
    _last_alert_ts = now

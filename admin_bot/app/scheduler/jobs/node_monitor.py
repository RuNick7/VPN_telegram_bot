"""
Node health monitoring.

Squad occupancy used to be checked here too, and alerted on when a squad went
past its cap. There is no cap any more -- everyone paying sits in one squad and
load is spread by balancers -- so "too many members" is not a fault condition.
Occupancy moved to `daily_squad_report`, which reports it once a day as
information rather than as an alarm.

What is left is genuinely urgent: a node that is offline or out of memory
should not wait until tomorrow.
"""

import logging
import time
import asyncio
from typing import Any, Dict, Optional

from tgvpn_shared.remnawave import APIError

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)
_last_alert_ts: float | None = None
_last_error_ts: float | None = None
ALERT_THROTTLE_SECONDS = 300
ERROR_THROTTLE_SECONDS = 300
REQUEST_RETRIES = 2
REQUEST_RETRY_DELAY_SECONDS = 1.0


def _extract_percent(data: Dict[str, Any], keys: list[str]) -> Optional[float]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 1:
            return value * 100
        return value
    return None


async def run_node_monitor() -> None:
    """Check node CPU/RAM and reachability, notify admins."""
    client = RemnawaveClient()
    alerts: list[str] = []
    try:
        async def _with_retry(label: str, call):
            """Retry `call()` on connectivity-shaped failures only."""
            last_exc: Exception | None = None
            for attempt in range(1, REQUEST_RETRIES + 1):
                try:
                    return await call()
                except APIError as exc:
                    last_exc = exc
                    # Retry only network timeout/connectivity-like failures.
                    if "ConnectTimeout" not in str(exc) and "Request failed" not in str(exc):
                        raise
                    if attempt >= REQUEST_RETRIES:
                        break
                    await asyncio.sleep(REQUEST_RETRY_DELAY_SECONDS * attempt)
            if last_exc:
                raise last_exc
            raise RuntimeError(f"Unexpected empty response for {label}")

        stats = await _with_retry("system stats", client.get_system_stats)
        nodes_stats = stats.get("nodes", {})
        total_online_nodes = nodes_stats.get("totalOnline")

        memory = stats.get("memory", {})
        total_mem = memory.get("total")
        used_mem = memory.get("used")
        if total_mem and used_mem:
            ram_percent = (used_mem / total_mem) * 100
            if ram_percent > settings.node_ram_max_percent:
                alerts.append(
                    f"RAM {ram_percent:.1f}% > {settings.node_ram_max_percent}% (system)"
                )

        nodes = await _with_retry("nodes", client.list_nodes)
        for node in nodes:
            name = node.get("name") or node.get("uuid", "unknown")

            ram = _extract_percent(
                node,
                ["ramUsage", "ram_usage", "memoryUsage", "memory_usage", "memUsage", "memoryPercent"],
            )
            if ram is not None and ram > settings.node_ram_max_percent:
                alerts.append(f"RAM {ram:.1f}% > {settings.node_ram_max_percent}% (node: {name})")

            if node.get("isConnected") is False:
                alerts.append(f"Node offline: {name}")

        if alerts:
            now = time.time()
            global _last_alert_ts
            if _last_alert_ts is None or now - _last_alert_ts >= ALERT_THROTTLE_SECONDS:
                header = "⚠️ Мониторинг нагрузки:"
                if total_online_nodes is not None:
                    header += f" (онлайн нод: {total_online_nodes})"
                text = header + "\n" + "\n".join(f"• {item}" for item in alerts)
                await send_admin_message(text)
                _last_alert_ts = now
            else:
                logger.info("Alerts throttled to avoid spam.")
    except Exception as e:
        is_connect_timeout = "ConnectTimeout" in str(e)
        if is_connect_timeout:
            logger.warning("Node monitor skipped due to Remnawave connect timeout: %s", e)
        else:
            logger.error("Node monitor failed: %s", e, exc_info=True)
        now = time.time()
        global _last_error_ts
        if _last_error_ts is None or now - _last_error_ts >= ERROR_THROTTLE_SECONDS:
            await send_admin_message(
                "❌ Ошибка мониторинга нод.\n"
                f"Причина: {e}\n"
                f"REMNAWAVE_BASE_URL: {settings.remnawave_base_url}"
            )
            _last_error_ts = now
    finally:
        await client.close()

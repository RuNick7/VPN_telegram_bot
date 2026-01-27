"""Node and squad monitoring job."""

import logging
import time
from typing import Any, Dict, Optional

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)
_last_alert_ts: float | None = None
ALERT_THROTTLE_SECONDS = 300


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
    """Check nodes CPU/RAM and squads size, notify admins."""
    client = RemnawaveClient()
    alerts: list[str] = []
    try:
        system_stats = await client.request("GET", "/system/stats")
        stats = system_stats.get("response", {})
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

        nodes_resp = await client.request("GET", "/nodes")
        nodes = nodes_resp.get("response", [])
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

        squads_resp = await client.request("GET", "/internal-squads")
        squads = squads_resp.get("response", {}).get("internalSquads", [])
        for squad in squads:
            name = squad.get("name") or squad.get("uuid", "unknown")
            members = (squad.get("info") or {}).get("membersCount")
            if isinstance(members, int) and members > settings.squad_max_users:
                alerts.append(
                    f"Squad '{name}' members {members} > {settings.squad_max_users}"
                )

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
        logger.error(f"Node monitor failed: {e}", exc_info=True)
    finally:
        await client.close()

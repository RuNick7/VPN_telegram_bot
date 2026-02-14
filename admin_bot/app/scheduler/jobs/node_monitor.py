"""Node and squad monitoring job."""

import logging
import time
import asyncio
from typing import Any, Dict, Optional

from app.api.client import RemnawaveClient
from app.api.errors import APIError
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


def _last_internal_squad(squads: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    prefix = settings.internal_squad_prefix
    best: tuple[int, Dict[str, Any]] | None = None
    for squad in squads:
        name = str(squad.get("name") or "")
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix):].lstrip("-_")
        try:
            idx = int(suffix)
        except (TypeError, ValueError):
            continue
        if best is None or idx > best[0]:
            best = (idx, squad)
    if best:
        return best[1]
    return squads[-1] if squads else None


async def run_node_monitor() -> None:
    """Check nodes CPU/RAM and squads size, notify admins."""
    client = RemnawaveClient()
    alerts: list[str] = []
    try:
        async def _request_with_retry(endpoint: str) -> Dict[str, Any]:
            last_exc: Exception | None = None
            for attempt in range(1, REQUEST_RETRIES + 1):
                try:
                    return await client.request("GET", endpoint)
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
            raise RuntimeError(f"Unexpected empty response for endpoint {endpoint}")

        system_stats = await _request_with_retry("/system/stats")
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

        nodes_resp = await _request_with_retry("/nodes")
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

        squads_resp = await _request_with_retry("/internal-squads")
        squads = squads_resp.get("response", {}).get("internalSquads", [])
        last_squad = _last_internal_squad(squads)
        for squad in squads:
            name = squad.get("name") or squad.get("uuid", "unknown")
            members = (squad.get("info") or {}).get("membersCount")
            if isinstance(members, int) and members > settings.internal_squad_max_users:
                alerts.append(
                    f"Squad '{name}' members {members} > {settings.internal_squad_max_users}"
                )
        if last_squad:
            name = last_squad.get("name") or last_squad.get("uuid", "unknown")
            members = (last_squad.get("info") or {}).get("membersCount")
            limit = settings.internal_squad_max_users
            if isinstance(members, int) and limit > 0:
                percent = (members / limit) * 100
                if percent >= 75:
                    alerts.append(
                        f"Last squad '{name}' is {percent:.0f}% full ({members}/{limit})"
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
                f"REMNAWAVE_BASE_URL: {settings.remnawave_api_url}"
            )
            _last_error_ts = now
    finally:
        await client.close()

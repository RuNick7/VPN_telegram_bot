"""LTE squad traffic limit enforcement."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.config.settings import settings
from app.db.repo.lte_limits import lte_limits_repo
from app.notify.admin import send_admin_message
from app.services.subscription_db import get_subscription_ends_map
from app.services.users import user_service

logger = logging.getLogger(__name__)


def _iso_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _extract_tg_id(user: dict[str, Any]) -> int | None:
    for key in ("telegramId", "telegram_id"):
        value = user.get(key)
        if isinstance(value, int):
            return value
    username = str(user.get("username") or "").strip()
    if username.isdigit():
        return int(username)
    return None


def _extract_user_squad_uuids(user: dict[str, Any]) -> list[str]:
    squads = user.get("activeInternalSquads") or []
    return [str(s.get("uuid")) for s in squads if s.get("uuid")]


def _extract_created_ts(user: dict[str, Any], fallback_ts: int) -> int:
    created_raw = user.get("createdAt") or user.get("created_at")
    if isinstance(created_raw, str) and created_raw.strip():
        normalized = created_raw.strip().replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(normalized).timestamp())
        except ValueError:
            return fallback_ts
    return fallback_ts


def _extract_usage_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    response = raw.get("response")
    if isinstance(response, list):
        return [row for row in response if isinstance(row, dict)]
    if isinstance(response, dict):
        for key in ("items", "rows", "usage", "stats"):
            value = response.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _extract_node_uuid(row: dict[str, Any]) -> str | None:
    for key in ("nodeUuid", "node_uuid", "nodeId", "node_id"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _extract_total_bytes(row: dict[str, Any]) -> int:
    for key in ("total", "totalBytes", "total_bytes", "bytes"):
        if key in row:
            return _to_int(row.get(key))
    download = _to_int(row.get("totalDownload") or row.get("download"))
    upload = _to_int(row.get("totalUpload") or row.get("upload"))
    return max(0, download + upload)


def _resolve_lte_node_uuids(nodes: list[dict[str, Any]]) -> set[str]:
    explicit = {str(item).strip() for item in settings.lte_limited_node_uuids if str(item).strip()}
    if explicit:
        return explicit

    keywords = [k.lower() for k in settings.lte_limited_node_name_keywords if k.strip()]
    if not keywords:
        return set()

    selected: set[str] = set()
    for node in nodes:
        node_uuid = node.get("uuid")
        node_name = str(node.get("name") or "").lower()
        if not node_uuid:
            continue
        if any(keyword in node_name for keyword in keywords):
            selected.add(str(node_uuid))
    return selected


async def _fetch_user_lte_usage_bytes(user_uuid: str, from_ts: int, to_ts: int, lte_nodes: set[str]) -> int:
    """
    Fetch user usage and aggregate only LTE nodes.

    Tries both old and new Remnawave endpoints.
    """
    if not lte_nodes:
        return 0

    params = {"start": _iso_date(from_ts), "end": _iso_date(to_ts)}
    endpoints = [
        f"/users/stats/usage/{user_uuid}/range",
        f"/users/stats/usage/range/{user_uuid}",
        f"/bandwidth-stats/users/{user_uuid}/legacy",
        f"/bandwidth-stats/users/{user_uuid}",
    ]
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            raw = await user_service.client.request("GET", endpoint, params=params)
            rows = _extract_usage_rows(raw)
            if not rows:
                return 0
            total = 0
            for row in rows:
                node_uuid = _extract_node_uuid(row)
                if node_uuid and node_uuid not in lte_nodes:
                    continue
                total += max(0, _extract_total_bytes(row))
            return total
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return 0


async def _list_all_users() -> list[dict[str, Any]]:
    page = 1
    size = 100
    users: list[dict[str, Any]] = []
    while True:
        response = await user_service.list_users(page=page, size=size)
        payload = response.get("response", {})
        batch = payload.get("users", []) or []
        if not isinstance(batch, list):
            break
        users.extend([item for item in batch if isinstance(item, dict)])
        total = payload.get("total")
        if not isinstance(total, int) or total <= page * size:
            break
        page += 1
    return users


async def run_lte_traffic_monitor() -> None:
    """Enforce LTE 30-day traffic limits and squad access."""
    if not settings.lte_traffic_monitor_enabled:
        return

    now = int(time.time())
    period_seconds = max(1, int(settings.lte_period_days)) * 86400
    free_bytes = max(0, int(settings.lte_free_gb_per_30d)) * 1024 * 1024 * 1024
    blocked_now = 0
    unblocked_now = 0

    try:
        lte_squad = await user_service._find_internal_squad_by_name(settings.lte_squad_name)
        lte_squad_uuid = (lte_squad or {}).get("uuid")
        if not lte_squad_uuid:
            logger.warning("LTE squad '%s' not found", settings.lte_squad_name)
            return

        free_squad = await user_service._find_internal_squad_by_name(settings.free_squad_name)
        free_squad_uuid = str((free_squad or {}).get("uuid") or "") or None

        nodes_resp = await user_service.client.request("GET", "/nodes")
        nodes = nodes_resp.get("response", []) or []
        lte_nodes = _resolve_lte_node_uuids(nodes if isinstance(nodes, list) else [])

        # Subscription_ends source-of-truth for paid access. If a user's
        # subscription has lapsed, LTE squad must be revoked regardless of
        # remaining paid GB balance: free mode means free servers only.
        ends_map = await get_subscription_ends_map()

        users = await _list_all_users()
        for user in users:
            user_uuid = user.get("uuid")
            if not user_uuid:
                continue
            tg_id = _extract_tg_id(user)
            if tg_id is None:
                continue

            initial_cycle_start = _extract_created_ts(user, now)
            state = await lte_limits_repo.create_if_missing(
                tg_id=tg_id,
                cycle_start_ts=initial_cycle_start,
            )
            cycle_start_ts = int(state.get("cycle_start_ts") or now)
            paid_balance = max(0, int(state.get("paid_balance_bytes") or 0))
            cycle_paid_spent = max(0, int(state.get("cycle_paid_spent_bytes") or 0))

            # Move cycle window by 30-day chunks; purchased balance is carried over.
            while now >= cycle_start_ts + period_seconds:
                cycle_start_ts += period_seconds
                cycle_paid_spent = 0

            usage_bytes = await _fetch_user_lte_usage_bytes(
                user_uuid=str(user_uuid),
                from_ts=cycle_start_ts,
                to_ts=now,
                lte_nodes=lte_nodes,
            )

            paid_needed = max(0, usage_bytes - free_bytes)
            if paid_needed > cycle_paid_spent:
                additional_needed = paid_needed - cycle_paid_spent
                additional_from_paid = min(additional_needed, paid_balance)
                paid_balance -= additional_from_paid
                cycle_paid_spent += additional_from_paid

            over_limit_bytes = max(0, paid_needed - cycle_paid_spent)
            sub_ends_ts = int(ends_map.get(tg_id, 0))
            subscription_expired = sub_ends_ts <= now
            # Subscription gate: lapsed users lose LTE even if balance > 0.
            should_block = bool(over_limit_bytes > 0 or subscription_expired)
            free_remaining = max(0, free_bytes - usage_bytes)
            remaining_bytes = max(0, free_remaining + paid_balance)

            squad_uuids = _extract_user_squad_uuids(user)
            has_lte = str(lte_squad_uuid) in squad_uuids
            in_free_only = bool(
                free_squad_uuid
                and free_squad_uuid in squad_uuids
                and not any(uuid != free_squad_uuid for uuid in squad_uuids if uuid)
            )
            desired_squads = list(squad_uuids)

            if should_block and has_lte:
                desired_squads = [uuid for uuid in squad_uuids if uuid != str(lte_squad_uuid)]
                await user_service._update_user_internal_squads(str(user_uuid), desired_squads)
                await user_service.force_disconnect_user(str(user_uuid))
                blocked_now += 1
            elif (
                not should_block
                and not has_lte
                and not in_free_only
            ):
                # Don't add LTE to a user that has been demoted to FREE only:
                # the subscription monitor owns that state and would just
                # remove LTE again on the next cycle.
                desired_squads.append(str(lte_squad_uuid))
                await user_service._update_user_internal_squads(str(user_uuid), desired_squads)
                unblocked_now += 1

            await lte_limits_repo.save_state(
                tg_id=tg_id,
                cycle_start_ts=cycle_start_ts,
                paid_balance_bytes=paid_balance,
                cycle_paid_spent_bytes=cycle_paid_spent,
                is_blocked=should_block,
                last_total_usage_bytes=usage_bytes,
                last_remaining_bytes=remaining_bytes,
            )

        if blocked_now or unblocked_now:
            await send_admin_message(
                "📶 LTE лимит-монитор:\n"
                f"• заблокировано: {blocked_now}\n"
                f"• разблокировано: {unblocked_now}\n"
                f"• окно: последние {settings.lte_period_days} дней\n"
                f"• бесплатный лимит: {settings.lte_free_gb_per_30d} ГБ"
            )
    except Exception as exc:
        logger.error("LTE traffic monitor failed: %s", exc, exc_info=True)
        await send_admin_message(
            "❌ Ошибка LTE лимит-монитора.\n"
            f"Причина: {exc}"
        )

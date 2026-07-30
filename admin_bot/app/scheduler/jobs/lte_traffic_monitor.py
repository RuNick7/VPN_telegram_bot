"""
Enforce LTE traffic quotas.

LTE is a metered squad: each cycle a user gets a free allowance, and can buy
extra traffic that carries over. When both are exhausted the LTE squad is
removed until the next cycle or the next top-up.

The accounting rule that governs this file: **the paid balance is only ever
adjusted by a delta.** A pass reads the balance, then makes several slow panel
calls, then writes back — and a purchase can land in that window. Writing a
recomputed absolute value would erase it. `legacy-main` shipped that bug
before fixing it, and `LteRepository.consume_balance` is shaped so the fixed
form is the only one available.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from tgvpn_shared.db import JobRunRepository, LteRepository, UserRepository
from tgvpn_shared.squads import SquadResolutionError, SquadRoles, resolve_squad_roles

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message
from app.scheduler.jobs.subscription_expire_monitor import (
    extract_squad_uuids,
    extract_telegram_id,
)

logger = logging.getLogger(__name__)

JOB_NAME = "lte_traffic_monitor"

_users = UserRepository()
_lte = LteRepository()
_jobs = JobRunRepository()

# Remnawave renamed its per-user usage endpoint across versions. The first one
# that answers is remembered so later users in the same pass skip the probing.
_USAGE_ENDPOINTS = (
    "/users/stats/usage/{uuid}/range",
    "/users/stats/usage/range/{uuid}",
    "/bandwidth-stats/users/{uuid}/legacy",
    "/bandwidth-stats/users/{uuid}",
)
_working_endpoint: str | None = None


def _iso_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _row_bytes(row: dict[str, Any]) -> int:
    """Total bytes in a usage row, however this panel version spells it."""
    for key in ("total", "totalBytes", "total_bytes", "bytes"):
        if key in row:
            return max(0, _to_int(row[key]))
    download = _to_int(row.get("totalDownload") or row.get("download"))
    upload = _to_int(row.get("totalUpload") or row.get("upload"))
    return max(0, download + upload)


def _row_node_uuid(row: dict[str, Any]) -> str | None:
    for key in ("nodeUuid", "node_uuid", "nodeId", "node_id"):
        if row.get(key):
            return str(row[key])
    return None


def _usage_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("items", "rows", "usage", "stats"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def resolve_lte_nodes(nodes: list[dict[str, Any]]) -> set[str]:
    """
    Which nodes count against the quota.

    Explicit UUIDs win outright; otherwise nodes are matched by name
    substring, which is the form a human-managed panel can actually maintain.
    An empty result means nothing is metered, and the caller treats that as
    "nothing to enforce" rather than "meter everything".
    """
    explicit = {uuid for uuid in settings.lte_node_uuids if uuid}
    if explicit:
        return explicit

    keywords = settings.lte_node_name_keywords
    if not keywords:
        return set()
    return {
        str(node["uuid"])
        for node in nodes
        if node.get("uuid")
        and any(keyword in str(node.get("name") or "").lower() for keyword in keywords)
    }


async def fetch_usage_bytes(client, user_uuid: str, since: int, until: int, nodes: set[str]) -> int:
    """Bytes this user spent on metered nodes within the window."""
    global _working_endpoint
    if not nodes:
        return 0

    params = {"start": _iso_date(since), "end": _iso_date(until)}
    candidates = list(_USAGE_ENDPOINTS)
    if _working_endpoint in candidates:
        candidates.remove(_working_endpoint)
        candidates.insert(0, _working_endpoint)

    last_error: Exception | None = None
    for template in candidates:
        endpoint = template.format(uuid=user_uuid)
        try:
            payload = await client.request("GET", endpoint, params=params)
        except Exception as exc:
            last_error = exc
            continue
        _working_endpoint = template
        rows = _usage_rows(payload.get("response", payload))
        return sum(
            _row_bytes(row)
            for row in rows
            if (_row_node_uuid(row) or "") in nodes or _row_node_uuid(row) is None
        )
    if last_error:
        raise last_error
    return 0


def settle_cycle(
    *,
    now: int,
    cycle_start: int,
    cycle_seconds: int,
    cycle_spent: int,
) -> tuple[int, int]:
    """
    Advance the quota window past every elapsed cycle.

    Returns `(cycle_start, cycle_spent)`. Whole cycles are skipped in one step
    rather than one per pass, so a user the monitor hasn't seen in months
    lands on the correct current window immediately. Spend resets; the
    purchased balance deliberately does not, because bought traffic belongs to
    the user rather than to a cycle.
    """
    if cycle_seconds <= 0:
        return cycle_start, cycle_spent
    elapsed_cycles = (now - cycle_start) // cycle_seconds
    if elapsed_cycles <= 0:
        return cycle_start, cycle_spent
    return cycle_start + elapsed_cycles * cycle_seconds, 0


def free_bytes_for(state: dict) -> int:
    """
    This user's free allowance per cycle, in bytes.

    A per-user override wins over the global setting. `None` means no override;
    `0` is a real one meaning no free traffic, which is why this checks for
    None rather than falsiness.
    """
    override = state.get("lte_free_gb_override")
    if override is None:
        return settings.lte_free_bytes_per_cycle
    return max(0, int(override)) * 1024**3


def plan_quota(
    *,
    usage_bytes: int,
    free_bytes: int,
    cycle_spent: int,
    paid_balance: int,
    subscription_active: bool,
) -> tuple[int, int, bool]:
    """
    Work out what this pass costs. Returns `(spend_delta, cycle_spent, blocked)`.

    Usage above the free allowance is charged to purchased traffic. Only the
    amount *newly* charged is returned as `spend_delta` -- the caller subtracts
    exactly that from the live balance, never a recomputed total.

    A lapsed subscription blocks regardless of remaining balance: free mode
    means free servers, and metered ones are not among them.
    """
    over_free = max(0, usage_bytes - free_bytes)
    newly_charged = max(0, min(over_free - cycle_spent, paid_balance))
    cycle_spent_after = cycle_spent + newly_charged
    unpaid = max(0, over_free - cycle_spent_after)
    return newly_charged, cycle_spent_after, bool(unpaid > 0 or not subscription_active)


async def _apply_squad(
    client, roles: SquadRoles, user_uuid: str, current: list[str], *, blocked: bool
) -> str | None:
    """Add or remove LTE membership. Returns 'blocked', 'unblocked', or None."""
    if not roles.lte_uuid:
        return None

    has_lte = roles.lte_uuid in current
    if blocked and has_lte:
        await client.set_user_squads([user_uuid], [u for u in current if u != roles.lte_uuid])
        await client.disconnect_user(user_uuid)
        return "blocked"

    if not blocked and not has_lte:
        # Never hand LTE to someone sitting on FREE only: the expiry monitor
        # owns that state and would strip it again on its next pass, leaving
        # the two jobs fighting each other every few minutes.
        if roles.tier_of(current) != "paid":
            return None
        await client.set_user_squads([user_uuid], [*current, roles.lte_uuid])
        return "unblocked"
    return None


async def _reconcile_user(
    client,
    roles: SquadRoles,
    user: dict[str, Any],
    *,
    telegram_id: int,
    subscription_ends: int,
    nodes: set[str],
    now: int,
) -> str | None:
    user_uuid = str(user["uuid"])

    state = await _lte.start_cycle_if_unset(telegram_id, now)
    if state is None:
        return None

    cycle_start = int(state["lte_cycle_start"] or now)
    cycle_spent = max(0, int(state["lte_cycle_spent_bytes"] or 0))
    paid_balance = max(0, int(state["lte_paid_balance_bytes"] or 0))

    rolled_start, cycle_spent = settle_cycle(
        now=now,
        cycle_start=cycle_start,
        cycle_seconds=settings.lte_cycle_seconds,
        cycle_spent=cycle_spent,
    )
    if rolled_start != cycle_start:
        await _lte.roll_cycle(telegram_id, rolled_start)
        cycle_start = rolled_start

    usage = await fetch_usage_bytes(client, user_uuid, cycle_start, now, nodes)
    spend_delta, cycle_spent, blocked = plan_quota(
        usage_bytes=usage,
        free_bytes=free_bytes_for(state),
        cycle_spent=cycle_spent,
        paid_balance=paid_balance,
        subscription_active=subscription_ends > now,
    )

    outcome = await _apply_squad(
        client, roles, user_uuid, extract_squad_uuids(user), blocked=blocked
    )

    await _lte.consume_balance(
        telegram_id,
        spent_delta_bytes=spend_delta,
        cycle_spent_bytes=cycle_spent,
        blocked=blocked,
        last_usage_bytes=usage,
    )
    return outcome


async def _run() -> tuple[int, int, int]:
    client = RemnawaveClient()
    blocked = unblocked = failed = 0
    try:
        roles = await resolve_squad_roles(
            client,
            free_name=settings.free_squad_name,
            lte_name=settings.lte_squad_name,
            paid_prefix=settings.internal_squad_prefix,
        )
        if not roles.lte_uuid:
            logger.info("LTE squad not present in the panel; nothing to enforce")
            return 0, 0, 0

        nodes = resolve_lte_nodes(await client.list_nodes())
        if not nodes:
            logger.warning(
                "No LTE nodes matched LTE_NODE_UUIDS/LTE_NODE_NAME_KEYWORDS; quota is not enforced"
            )
            return 0, 0, 0

        ends_by_telegram_id = await _users.get_subscription_ends_map()
        now = int(time.time())

        async for user in client.iter_all_users():
            telegram_id = extract_telegram_id(user)
            if telegram_id is None or not user.get("uuid"):
                continue
            try:
                outcome = await _reconcile_user(
                    client,
                    roles,
                    user,
                    telegram_id=telegram_id,
                    subscription_ends=ends_by_telegram_id.get(telegram_id, 0),
                    nodes=nodes,
                    now=now,
                )
                if outcome == "blocked":
                    blocked += 1
                elif outcome == "unblocked":
                    unblocked += 1
            except Exception as exc:
                failed += 1
                logger.warning("LTE monitor: tg_id=%s failed: %s", telegram_id, exc)

        return blocked, unblocked, failed
    finally:
        await client.close()


async def run_lte_traffic_monitor() -> None:
    """Scheduled entry point. Never raises -- the scheduler must keep ticking."""
    if not settings.lte_enabled:
        return

    started = time.monotonic()
    try:
        blocked, unblocked, failed = await _run()
    except SquadResolutionError as exc:
        await _jobs.record_failure(JOB_NAME, str(exc))
        logger.error("LTE monitor cannot run: %s", exc)
        await send_admin_message(f"❌ LTE-монитор не может работать.\n{exc}")
        return
    except Exception as exc:
        await _jobs.record_failure(JOB_NAME, str(exc))
        logger.error("LTE traffic monitor failed: %s", exc, exc_info=True)
        await send_admin_message(f"❌ Ошибка LTE-монитора.\nПричина: {exc}")
        return

    await _jobs.record_success(JOB_NAME, int((time.monotonic() - started) * 1000))
    if blocked or unblocked or failed:
        lines = [
            "📶 LTE лимит-монитор:",
            f"• заблокировано: {blocked}",
            f"• разблокировано: {unblocked}",
            f"• окно: {settings.lte_cycle_days} дн., бесплатно {settings.lte_free_gb_per_cycle} ГБ",
        ]
        if failed:
            lines.append(f"• ошибок по пользователям: {failed}")
        await send_admin_message("\n".join(lines))

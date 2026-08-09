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

from aiogram import Bot
from tgvpn_shared.db import JobRunRepository, LteRepository, UserRepository
from tgvpn_shared.remnawave.client import panel_ref
from tgvpn_shared.lte_quota import (
    TRAFFIC_LABEL,
    format_traffic,
    free_bytes_for,
    low_traffic_threshold,
    plan_quota,
    remaining_bytes,
    settle_cycle,
)
from tgvpn_shared.squads import SquadResolutionError, SquadRoles, resolve_squad_roles

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message
from app.scheduler.jobs.subscription_expire_monitor import (
    Subject,
    extract_squad_uuids,
    resolve_subject,
    warn_about_stuck_accounts,
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

# Said once per process, not once per user per pass -- the monitor runs every
# few minutes and would otherwise write the same line hundreds of times a day.
_warned_unattributed = False


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


# Where a chart-shaped answer keeps its per-node totals. `series` first: it and
# `topNodes` carry the same figures, and counting both would double every
# reading.
_NODE_SERIES_KEYS = ("series", "topNodes")


def usage_by_node(payload: Any) -> list[tuple[str | None, int]]:
    """
    Usage as `(node ref, bytes)` pairs, however this panel version reports it.

    Two shapes exist and which one arrives is not ours to choose. Remnawave
    answers `/bandwidth-stats` with a chart -- `series`, one entry per node,
    naming the node under plain `uuid` and carrying its `total`. The older
    endpoints answer with a flat list whose rows name their node under one of
    the `node*` spellings.

    Reading them apart rather than through one key list is what makes the
    plain `uuid` safe to trust: in a chart series it is always a node, while in
    a flat usage row it may well be the user the row belongs to, and charging
    a quota against a misread identifier is worse than reading nothing.

    A `None` node means the payload did not say; the caller decides what an
    unattributed reading is worth.
    """
    if isinstance(payload, dict):
        for key in _NODE_SERIES_KEYS:
            series = payload.get(key)
            if isinstance(series, list):
                return [
                    (str(entry.get("uuid") or entry.get("id") or "") or None, _row_bytes(entry))
                    for entry in series
                    if isinstance(entry, dict)
                ]
    return [(_row_node_uuid(row), _row_bytes(row)) for row in _usage_rows(payload)]


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
        panel_ref(node)
        for node in nodes
        if panel_ref(node)
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
        return sum_metered(usage_by_node(payload.get("response", payload)), nodes)
    if last_error:
        raise last_error
    return 0


def sum_metered(rows: list[tuple[str | None, int]], nodes: set[str]) -> int:
    """
    Add up only what was spent on metered nodes.

    When the payload attributes its readings, unmatched nodes are dropped --
    otherwise a user's traffic on ordinary servers would be charged against
    their LTE allowance, which is the opposite of what the squad is for.

    When nothing is attributed the whole total is counted, because a panel
    that reports one undifferentiated figure would otherwise be metered at
    zero forever -- silently, which is exactly how this was broken. That
    compromise is stated in the log rather than left to be discovered.
    """
    global _warned_unattributed

    attributed = [(node, count) for node, count in rows if node]
    if attributed:
        return sum(count for node, count in attributed if node in nodes)

    total = sum(count for _, count in rows)
    if total and not _warned_unattributed:
        _warned_unattributed = True
        logger.warning(
            "Panel usage reports no per-node breakdown; every node counts "
            "against the LTE quota"
        )
    return total



def format_low_traffic_warning(threshold_mb: int, remaining: int) -> str:
    """The message a user gets as their metered traffic runs low."""
    if remaining <= 0:
        return (
            f"🚫 <b>{TRAFFIC_LABEL} закончился</b>\n\n"
            "Остальные серверы работают как обычно.\n"
            "Докупить трафик: /traffic"
        )
    return (
        f"⚠️ <b>Заканчивается {TRAFFIC_LABEL.lower()}</b>\n\n"
        f"Осталось примерно <b>{format_traffic(remaining)}</b> "
        f"(порог {threshold_mb} МБ).\n\n"
        "Докупить трафик: /traffic"
    )


async def _set_notified(subject: Subject, threshold_mb: int) -> None:
    if subject.telegram_id is not None:
        await _lte.set_low_traffic_notified(subject.telegram_id, threshold_mb)
    elif subject.user_id:
        await _lte.set_low_traffic_notified_by_user_id(subject.user_id, threshold_mb)


async def _maybe_warn_low_traffic(
    subject: Subject, *, remaining: int, already_notified_mb: int
) -> None:
    """
    Warn once per threshold crossed, and re-arm when the balance recovers.

    The monitor runs every few minutes, so sending on every pass below the
    threshold would be a message every five minutes until the user topped up.

    A user with no Telegram account -- one who signed up on the website --
    still has the flag moved, so the accounting stays right; they simply see
    the balance in the cabinet instead of getting a message.
    """
    threshold = low_traffic_threshold(remaining)
    if threshold == already_notified_mb:
        return

    # Recovered above every threshold -- clear the flag so the next slide
    # downward warns again instead of staying silent.
    if threshold == 0:
        await _set_notified(subject, 0)
        return

    if subject.telegram_id is not None:
        try:
            await _notify_user(
                subject.telegram_id, format_low_traffic_warning(threshold, remaining)
            )
        except Exception as exc:
            # A user who blocked the bot must not stop the monitor, but the
            # flag is still moved so we don't retry them every pass.
            logger.info(
                "Не удалось отправить предупреждение о трафике %s: %s",
                subject.telegram_id, exc,
            )
    await _set_notified(subject, threshold)


async def _notify_user(telegram_id: int, text: str) -> None:
    """
    Message a customer from user_bot, which is the bot they actually talk to.

    A fresh Bot per send: this fires rarely, and a long-lived session owned by
    the scheduler would outlive the job and leak on shutdown.
    """
    if not settings.user_bot_token:
        logger.warning("USER_BOT_TOKEN не задан; предупреждение о трафике не отправлено")
        return
    bot = Bot(token=settings.user_bot_token.strip())
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML")
    finally:
        await bot.session.close()


async def _apply_squad(
    client,
    roles: SquadRoles,
    user_uuid: str,
    current: list[str],
    *,
    blocked: bool,
    nodes: set[str] | None = None,
    still_flowing: bool = False,
) -> str | None:
    """
    Add or remove LTE membership.

    Returns 'blocked', 'unblocked', 'recut', or None.
    """
    if not roles.lte_uuid:
        return None

    has_lte = roles.lte_uuid in current
    if blocked and has_lte:
        # Membership first, and the cut second. A node is told what a user may
        # reach only when the panel pushes it, and dropping somebody from a
        # squad is recorded without being pushed -- so a block on its own left
        # the tunnel running, and dropping the session on its own let the
        # client, still listed in the node's inbound, back in within five
        # seconds. `disconnect_user` re-pushes the membership as its last act,
        # which is why the membership has to be right before it is called.
        #
        # Earlier versions had this the other way round for a reason that
        # turned out to be about the old disable/enable flip, not about the
        # drop. Both orders were tried against a live client; only this one
        # held. See `RemnawaveClient.disconnect_user`.
        remaining = [u for u in current if u != roles.lte_uuid]
        # The panel rejects an empty squad list outright -- HTTP 500, errorCode
        # A088 -- so somebody holding nothing but LTE cannot simply have it
        # taken away. FREE is what "no entitlement left" means everywhere else
        # here, so it is the floor.
        if not remaining and roles.free_uuid:
            remaining = [roles.free_uuid]
        await client.set_user_squads([user_uuid], remaining)

        # Only the metered nodes are dropped. The quota is spent there, and a
        # subscriber who exhausts it still pays for the ordinary servers --
        # cutting those too would be a bug wearing an enforcement costume.
        await client.disconnect_user(user_uuid, node_uuids=sorted(nodes or []))
        return "blocked"

    if blocked and still_flowing:
        # Out of the squad already, and still moving bytes on a metered node.
        # That can only mean the node is holding an entitlement the panel no
        # longer records, and nothing above will notice: the membership is
        # what it should be, so the block looks applied and this user is
        # skipped every pass, forever.
        #
        # Every account blocked by the version before this one can be sitting
        # in exactly that state, because stripping a squad was never pushed.
        # Cutting again is what pushes it.
        logger.warning(
            "%s is blocked and still passing traffic on a metered node; cutting again",
            user_uuid,
        )
        await client.disconnect_user(user_uuid, node_uuids=sorted(nodes or []))
        return "recut"

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
    subject: Subject,
    nodes: set[str],
    now: int,
) -> str | None:
    user_uuid = panel_ref(user)
    telegram_id = subject.telegram_id

    if telegram_id is not None:
        state = await _lte.start_cycle_if_unset(telegram_id, now)
    elif subject.user_id:
        state = await _lte.start_cycle_if_unset_by_user_id(subject.user_id, now)
    else:
        return None
    if state is None:
        return None
    # The row may have been reached by Telegram ID; keep the internal id so
    # the writes below can use it when there is no Telegram ID.
    subject.user_id = subject.user_id or (state.get("id") or None)

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
        if telegram_id is not None:
            await _lte.roll_cycle(telegram_id, rolled_start)
        elif subject.user_id:
            await _lte.roll_cycle_by_user_id(subject.user_id, rolled_start)
        cycle_start = rolled_start

    usage = await fetch_usage_bytes(client, user_uuid, cycle_start, now, nodes)
    spend_delta, cycle_spent, blocked = plan_quota(
        usage_bytes=usage,
        free_bytes=free_bytes_for(state, settings.lte_free_gb_per_cycle),
        cycle_spent=cycle_spent,
        paid_balance=paid_balance,
        subscription_active=subject.subscription_ends > now,
    )

    # Usage on the metered nodes moved since the last pass. For somebody who
    # should already be cut off, that is the only evidence available that the
    # node disagrees -- and it costs nothing, the figure is fetched anyway.
    outcome = await _apply_squad(
        client,
        roles,
        user_uuid,
        extract_squad_uuids(user),
        blocked=blocked,
        nodes=nodes,
        still_flowing=usage > max(0, int(state.get("lte_last_usage_bytes") or 0)),
    )

    consume_kwargs = dict(
        spent_delta_bytes=spend_delta,
        cycle_spent_bytes=cycle_spent,
        blocked=blocked,
        last_usage_bytes=usage,
    )
    if telegram_id is not None:
        written = await _lte.consume_balance(telegram_id, **consume_kwargs)
    else:
        written = await _lte.consume_balance_by_user_id(subject.user_id, **consume_kwargs)

    await _maybe_warn_low_traffic(
        subject,
        remaining=remaining_bytes(
            usage_bytes=usage,
            free_bytes=free_bytes_for(state, settings.lte_free_gb_per_cycle),
            paid_balance=int((written or {}).get("lte_paid_balance_bytes") or 0),
        ),
        already_notified_mb=int(state.get("lte_low_traffic_notified_mb") or 0),
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
            paid_name=settings.paid_squad_name,
        )
        if not roles.lte_uuid:
            logger.info("LTE squad not present in the panel; nothing to enforce")
            return 0, 0, 0

        await warn_about_stuck_accounts(client)

        nodes = resolve_lte_nodes(await client.list_nodes())
        if not nodes:
            logger.warning(
                "No LTE nodes matched LTE_NODE_UUIDS/LTE_NODE_NAME_KEYWORDS; quota is not enforced"
            )
            return 0, 0, 0

        ends_by_telegram_id = await _users.get_subscription_ends_map()
        # Second index, by panel UUID. Without it an account created on the
        # website -- which has no Telegram ID -- was skipped entirely: no
        # metering, no blocking when the quota ran out, no warnings.
        rows_by_panel_uuid = await _users.get_subscription_map_by_panel_uuid()
        now = int(time.time())

        async for user in client.iter_all_users():
            # `panel_ref`, not `user["uuid"]`. A newer panel identifies
            # accounts by a numeric `id` and has no `uuid` field at all, so
            # reading that key skipped every single user -- no metering, no
            # blocking, and a run that recorded success either way.
            if not panel_ref(user):
                continue
            subject = resolve_subject(user, ends_by_telegram_id, rows_by_panel_uuid)
            if subject is None:
                continue
            telegram_id = subject.telegram_id or subject.user_id
            try:
                outcome = await _reconcile_user(
                    client,
                    roles,
                    user,
                    subject=subject,
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
    """
    Scheduled entry point. Never raises -- the scheduler must keep ticking.

    Guarded from the outside, for the reason spelled out on the expiry
    monitor's entry point: the handlers below record failures and message the
    admin chat, and both of those can fail on their own during the outage they
    are reporting.
    """
    try:
        await _run_and_report()
    except Exception as exc:
        logger.error("LTE monitor entry point failed: %s", exc, exc_info=True)


async def _run_and_report() -> None:
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
            # The failure alerts below stay on the technical name on purpose --
            # they are read next to `lte_traffic_monitor` in the logs.
            "📶 Монитор трафика белых списков:",
            f"• заблокировано: {blocked}",
            f"• разблокировано: {unblocked}",
            f"• окно: {settings.lte_cycle_days} дн., бесплатно {settings.lte_free_gb_per_cycle} ГБ",
        ]
        if failed:
            lines.append(f"• ошибок по пользователям: {failed}")
        await send_admin_message("\n".join(lines))

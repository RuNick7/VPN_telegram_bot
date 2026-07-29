"""
Move users between paid and FREE squads as their subscriptions lapse and renew.

Why a job owns this at all: the FREE tier means a lapsed user keeps a working
panel account on limited servers rather than losing access outright. Remnawave
cannot express "expire into a different squad" -- confirmed against its API --
so the panel account is held open and this job becomes the thing that actually
enforces expiry.

That makes its silence dangerous: if it stops running, nobody is ever demoted
and every expired user keeps paid access indefinitely, with nothing looking
wrong. Three things guard against that, and they are the reason this exists
rather than a straight port of `legacy-main`'s version:

- every run records success or failure in `job_runs`, so the health monitor
  can alert on a job that has stopped succeeding (see `service_health_monitor`);
- `run_catchup_sweep()` runs once at startup, so a restart after downtime
  reconciles immediately instead of waiting for the next tick;
- squad roles are resolved to UUIDs up front and a missing FREE squad aborts
  the run loudly, instead of being skipped with a log line nobody reads.

The pass is idempotent: a user already in the right state generates no API
call.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from tgvpn_shared.db import JobRunRepository, LteRepository, UserRepository
from tgvpn_shared.squads import (
    SquadResolutionError,
    SquadRoles,
    get_or_create_internal_squad,
    resolve_squad_roles,
)

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)

JOB_NAME = "subscription_expire_monitor"

_users = UserRepository()
_lte = LteRepository()
_jobs = JobRunRepository()

# Only report a run that actually changed something or hit errors; a quiet
# reconciliation every five minutes is not news.
_REPORT_PREVIEW_LIMIT = 5


def extract_telegram_id(user: dict[str, Any]) -> int | None:
    """
    A panel user's Telegram ID, falling back to the username.

    Accounts created by user_bot are named after the Telegram ID, and older
    ones predate `telegramId` being populated -- so the username is the only
    link back to our database for them.
    """
    for key in ("telegramId", "telegram_id"):
        value = user.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    username = str(user.get("username") or "").strip()
    return int(username) if username.isdigit() else None


def extract_squad_uuids(user: dict[str, Any]) -> list[str]:
    return [str(s["uuid"]) for s in (user.get("activeInternalSquads") or []) if s.get("uuid")]


def plan_membership(
    roles: SquadRoles,
    current: list[str],
    *,
    subscription_active: bool,
    paid_squad_uuid: str | None,
) -> list[str] | None:
    """
    Decide the user's squads, or None when they are already correct.

    Returning None for "no change" is what keeps the pass idempotent -- with
    hundreds of users and a five-minute interval, re-sending an identical
    membership every time would be most of the job's API traffic.

    Squads outside our three roles are preserved: an operator may have put
    someone in a custom squad by hand, and that is not ours to undo.
    """
    preserved = roles.strip_managed(current)

    if not subscription_active:
        # Expired: FREE only. LTE goes too -- free mode means free servers,
        # regardless of any purchased traffic left over.
        desired = [*preserved, roles.free_uuid]
    else:
        if not paid_squad_uuid:
            return None
        keep_lte = bool(roles.lte_uuid and roles.lte_uuid in current)
        desired = [*preserved, paid_squad_uuid]
        if keep_lte:
            desired.append(roles.lte_uuid)

    return None if set(desired) == set(current) else desired


async def _reconcile_user(
    client,
    roles: SquadRoles,
    user: dict[str, Any],
    subscription_ends: int,
    now: int,
) -> str | None:
    """Apply the plan for one user. Returns 'demoted', 'promoted', or None."""
    user_uuid = user.get("uuid")
    telegram_id = extract_telegram_id(user)
    if not user_uuid or telegram_id is None:
        return None

    current = extract_squad_uuids(user)
    active = subscription_ends > now

    paid_uuid = None
    if active and roles.tier_of(current) != "paid":
        # Only reach for a squad when the user actually needs one; this can
        # create a squad, so it must not run on every pass.
        squad, _created = await get_or_create_internal_squad(
            client,
            max_users=settings.internal_squad_max_users,
            prefix=settings.internal_squad_prefix,
        )
        paid_uuid = str((squad or {}).get("uuid") or "") or None
    elif active:
        paid_uuid = next(iter(set(current) & roles.paid_uuids), None)

    desired = plan_membership(
        roles, current, subscription_active=active, paid_squad_uuid=paid_uuid
    )
    if desired is None:
        # Already correct -- still record the tier so reporting is accurate.
        await _lte.set_squad_tier(telegram_id, "paid" if active else "free")
        return None

    await client.set_user_squads([str(user_uuid)], desired)

    if not active:
        # Membership changes don't drop existing connections, so without this
        # a demoted user keeps paid servers until their client reconnects.
        await client.disconnect_user(str(user_uuid))
        await _lte.set_squad_tier(telegram_id, "free")
        logger.info("Demoted tg_id=%s to FREE (was %s)", telegram_id, current)
        return "demoted"

    await _lte.set_squad_tier(telegram_id, "paid")
    logger.info("Promoted tg_id=%s to paid squad %s", telegram_id, paid_uuid)
    return "promoted"


async def _run(reason: str) -> tuple[int, int, list[str]]:
    """One full reconciliation pass. Returns (demoted, promoted, failures)."""
    client = RemnawaveClient()
    demoted = promoted = 0
    failures: list[str] = []
    try:
        roles = await resolve_squad_roles(
            client,
            free_name=settings.free_squad_name,
            lte_name=settings.lte_squad_name if settings.lte_enabled else None,
            paid_prefix=settings.internal_squad_prefix,
        )

        ends_by_telegram_id = await _users.get_subscription_ends_map()
        now = int(time.time())

        async for user in client.iter_all_users():
            telegram_id = extract_telegram_id(user)
            if telegram_id is None:
                continue
            try:
                outcome = await _reconcile_user(
                    client, roles, user, ends_by_telegram_id.get(telegram_id, 0), now
                )
                if outcome == "demoted":
                    demoted += 1
                elif outcome == "promoted":
                    promoted += 1
            except Exception as exc:
                # One unreconcilable user must not abort the sweep -- the rest
                # still need enforcing.
                failures.append(f"{telegram_id}: {exc}")
                logger.warning("Failed to reconcile tg_id=%s: %s", telegram_id, exc)

        logger.info(
            "Expire monitor (%s): demoted=%d promoted=%d failures=%d",
            reason, demoted, promoted, len(failures),
        )
        return demoted, promoted, failures
    finally:
        await client.close()


def _format_report(reason: str, demoted: int, promoted: int, failures: list[str]) -> str:
    lines = [
        f"🛡 Монитор подписок ({reason}):",
        f"• понижено в FREE: {demoted}",
        f"• возвращено в платный: {promoted}",
    ]
    if failures:
        lines.append(f"• ошибок: {len(failures)}")
        lines.extend(f"  — {item}" for item in failures[:_REPORT_PREVIEW_LIMIT])
        if len(failures) > _REPORT_PREVIEW_LIMIT:
            lines.append(f"  … и ещё {len(failures) - _REPORT_PREVIEW_LIMIT}")
    return "\n".join(lines)


async def run_subscription_expire_monitor(reason: str = "по расписанию") -> None:
    """Scheduled entry point. Never raises -- the scheduler must keep ticking."""
    if not settings.free_tier_enabled:
        return

    started = time.monotonic()
    try:
        demoted, promoted, failures = await _run(reason)
    except SquadResolutionError as exc:
        # Configuration is wrong, not a transient failure. Say so plainly:
        # without a FREE squad there is nowhere to demote anyone to, and every
        # expired user is keeping paid access right now.
        await _jobs.record_failure(JOB_NAME, str(exc))
        logger.error("Expire monitor cannot run: %s", exc)
        await send_admin_message(
            f"❌ Монитор подписок не может работать.\n{exc}\n\n"
            "Пока это не исправлено, просроченные подписки не отключаются."
        )
        return
    except Exception as exc:
        await _jobs.record_failure(JOB_NAME, str(exc))
        logger.error("Expire monitor failed: %s", exc, exc_info=True)
        await send_admin_message(f"❌ Ошибка монитора подписок.\nПричина: {exc}")
        return

    await _jobs.record_success(JOB_NAME, int((time.monotonic() - started) * 1000))
    if demoted or promoted or failures:
        await send_admin_message(_format_report(reason, demoted, promoted, failures))


async def run_catchup_sweep() -> None:
    """
    Reconcile once at startup, before the first scheduled tick.

    Without this, a service that was down for an hour leaves every user who
    expired in that window on paid squads until the next interval comes
    around. The sweep is the same pass, so it is equally idempotent.
    """
    if not settings.free_tier_enabled:
        return
    logger.info("Running catch-up reconciliation sweep at startup")
    await run_subscription_expire_monitor(reason="догоняющий проход")

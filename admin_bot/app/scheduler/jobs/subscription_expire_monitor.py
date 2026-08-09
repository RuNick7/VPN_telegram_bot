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
from tgvpn_shared.free_tier import plan_panel_update
from tgvpn_shared.remnawave.client import panel_ref
from tgvpn_shared.squads import (
    SquadResolutionError,
    SquadRoles,
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


class Subject:
    """
    Which of our users a panel account belongs to, and what we know about them.

    Two ways in, because there are two kinds of account. One created by the bot
    carries a Telegram ID; one created on the website does not, and is found by
    matching the panel UUID against `users.remnawave_uuid` instead. Before this
    existed, a website account fell out of the loop entirely -- never demoted
    when it lapsed, never tagged, and so never cleaned up.
    """

    __slots__ = ("telegram_id", "user_id", "subscription_ends")

    def __init__(self, telegram_id: int | None, user_id: str | None, subscription_ends: int):
        self.telegram_id = telegram_id
        self.user_id = user_id
        self.subscription_ends = subscription_ends


def resolve_subject(
    user: dict[str, Any],
    ends_by_telegram_id: dict[int, int],
    rows_by_panel_uuid: dict[str, dict],
) -> Subject | None:
    """
    Match a panel account to our database, by Telegram ID or by panel UUID.

    Returns None when neither matches, which means the account is not one of
    ours -- an operator created it by hand, say -- and must be left alone.
    """
    telegram_id = extract_telegram_id(user)
    if telegram_id is not None and telegram_id in ends_by_telegram_id:
        return Subject(telegram_id, None, ends_by_telegram_id[telegram_id])

    row = rows_by_panel_uuid.get(panel_ref(user))
    if row is not None:
        return Subject(
            row.get("telegram_id"),
            str(row["id"]),
            int(row.get("subscription_ends") or 0),
        )

    # A Telegram-named account with no row is still ours to manage: the bot
    # created it, and our row may simply be missing. Treat it as expired.
    if telegram_id is not None:
        return Subject(telegram_id, None, 0)
    return None


async def record_tier(subject: Subject, tier: str) -> None:
    """Store the tier by whichever handle this user has."""
    if subject.telegram_id is not None:
        await _lte.set_squad_tier(subject.telegram_id, tier)
    elif subject.user_id:
        await _lte.set_squad_tier_by_user_id(subject.user_id, tier)


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


async def warn_about_stuck_accounts(client) -> list[str]:
    """
    Put back anyone an earlier session-drop left disabled, and shout if it fails.

    Dropping a session means disabling the account for an instant, because the
    panel offers nothing narrower -- see `RemnawaveClient.disconnect_user`. When
    the second half of that does not land, the customer has no access at all,
    which is why both monitors call this *before* their pass rather than after:
    putting somebody back costs one call and matters more than reconciliation.

    It lives here rather than beside the traffic monitor only because that
    module already imports this one, and the reverse would be a cycle.
    """
    stuck = await client.flush_pending_enables()
    if stuck:
        await send_admin_message(
            "❗️ Не удалось включить обратно в панели: "
            + ", ".join(stuck)
            + "\nУ этих аккаунтов сейчас нет доступа. Включите вручную."
        )
    return stuck


async def _reconcile_user(
    client,
    roles: SquadRoles,
    user: dict[str, Any],
    subject: Subject,
    now: int,
) -> str | None:
    """Apply the plan for one user. Returns 'demoted', 'promoted', or None."""
    # `panel_ref`, not `user["uuid"]`. A newer panel names accounts with a
    # numeric `id` and carries no `uuid` at all, and reading that key returned
    # None for every user -- nobody demoted when their subscription lapsed,
    # nobody promoted when they paid, and no sign of it anywhere.
    user_uuid = panel_ref(user)
    if not user_uuid:
        return None

    telegram_id = subject.telegram_id
    current = extract_squad_uuids(user)
    active = subject.subscription_ends > now

    # One squad for everyone who is paying; resolved up front, so there is
    # nothing to look up or create per user any more.
    paid_uuid = roles.paid_uuid if active else None

    tier = "paid" if active else "free"

    # Squad membership alone is not enough: an account whose expireAt has
    # already passed is expired to Remnawave whatever squad it holds, so a
    # user who lapsed *before* the FREE tier was switched on would land in the
    # FREE squad and still have nothing working. Push the date forward and tag
    # the tier so it is visible in the panel.
    panel_update = plan_panel_update(user=user, tier=tier, now=now)
    if panel_update:
        await client.update_user({"uuid": str(user_uuid), **panel_update})

    desired = plan_membership(
        roles, current, subscription_active=active, paid_squad_uuid=paid_uuid
    )
    if desired is None:
        # Already correct -- still record the tier so reporting is accurate,
        # and so the free-squad cleanup can see how long they have been there.
        await record_tier(subject, tier)
        return None

    # The membership change goes first and the drop last. A node is told what
    # a user may reach only when the panel pushes it, and a squad change is
    # recorded without being pushed; `disconnect_user` ends by re-pushing
    # whatever squads the user holds at that moment, so the demotion has to be
    # in place before it runs. See the same ordering, and the evidence for it,
    # in the traffic monitor.
    await client.set_user_squads([str(user_uuid)], desired)

    if not active:
        # Membership changes don't drop existing connections, so without this
        # a demoted user keeps paid servers until their client reconnects.
        await client.disconnect_user(str(user_uuid))

    if not active:
        await record_tier(subject, "free")
        logger.info("Demoted %s to FREE (was %s)", telegram_id or subject.user_id, current)
        return "demoted"

    await record_tier(subject, "paid")
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
            paid_name=settings.paid_squad_name,
        )

        # Before anything else: a demotion drops the session by disabling the
        # account for an instant, and an account left disabled has no access at
        # all. Recovering one matters more than this pass's reconciliation.
        await warn_about_stuck_accounts(client)

        ends_by_telegram_id = await _users.get_subscription_ends_map()
        # Second index, by panel UUID, so accounts with no Telegram ID -- a
        # website signup -- are reconciled too rather than silently skipped.
        rows_by_panel_uuid = await _users.get_subscription_map_by_panel_uuid()
        now = int(time.time())

        async for user in client.iter_all_users():
            subject = resolve_subject(user, ends_by_telegram_id, rows_by_panel_uuid)
            if subject is None:
                # Not one of ours -- an account an operator made by hand.
                continue
            label = subject.telegram_id or subject.user_id
            try:
                outcome = await _reconcile_user(client, roles, user, subject, now)
                if outcome == "demoted":
                    demoted += 1
                elif outcome == "promoted":
                    promoted += 1
            except Exception as exc:
                # One unreconcilable user must not abort the sweep -- the rest
                # still need enforcing.
                failures.append(f"{label}: {exc}")
                logger.warning("Failed to reconcile %s: %s", label, exc)

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
    """
    Scheduled entry point. Never raises -- the scheduler must keep ticking.

    The guarantee is enforced here rather than assumed of the body, because
    the body's own failure path can fail: a panel timeout was handled exactly
    as intended, then recording that failure hit a database which was down
    too, and the second exception escaped as an unhandled task exception. An
    outage that takes both at once is precisely when this must not compound.
    """
    try:
        await _run_and_report(reason)
    except Exception as exc:
        logger.error("Expire monitor entry point failed: %s", exc, exc_info=True)


async def _run_and_report(reason: str) -> None:
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

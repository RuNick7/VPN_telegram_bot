"""
Deciding which of our users still need a panel account.

Pure functions only; `scripts/provision_panel_users.py` supplies the I/O.
Split for the same reason as the identity backfill: a one-off script against
live data that cannot be exercised offline is a script nobody exercises.

This is the other half of the identity work. `identity_backfill` walks the
*panel* and attaches accounts to users; this walks our *database* and finds
users with no panel account at all -- people who exist here and have nothing
to connect with. That happens when the panel is rebuilt, when accounts were
deleted by the inactive-user cleanup, or on a first deployment against a fresh
panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Matches identity.panel_username_for; duplicated rather than imported so the
# script stays runnable from a checkout without the package installed.
OWN_USERNAME_PREFIX = "u-"


def panel_username_for(user_id: str) -> str:
    compact = str(user_id).replace("-", "")
    return f"{OWN_USERNAME_PREFIX}{compact[:16]}"


@dataclass(frozen=True)
class Provision:
    """One user's outcome."""

    user_id: str
    telegram_id: int | None
    username: str
    expire_ts: int
    # Days to grant because this user has never had a subscription.
    trial_days: int = 0
    create: bool = False
    reason: str = ""

    @property
    def is_trial(self) -> bool:
        return self.trial_days > 0


@dataclass
class Plan:
    to_create: list[Provision] = field(default_factory=list)
    already_have: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "users": len(self.to_create) + len(self.already_have) + len(self.skipped),
            "create": len(self.to_create),
            "with_trial": sum(1 for item in self.to_create if item.is_trial),
            "already_have": len(self.already_have),
            "skipped": len(self.skipped),
        }


def plan_provisioning(
    db_rows: list[dict],
    panel_uuids: set[str],
    panel_usernames: set[str],
    *,
    now: int,
    trial_days: int,
) -> Plan:
    """
    Work out which users need a panel account created, and with what expiry.

    A user is considered to already have one when their stored UUID is present
    in the panel, or when a panel account exists under either name we would
    look them up by. Checking names as well as UUIDs is what stops this
    creating a *second* account for someone whose link was simply never
    recorded -- exactly the population `identity_backfill` exists to repair.

    Expiry is whatever our database says, which is authoritative: the panel is
    being rebuilt from it, not consulted. A user who has never had a
    subscription is given the trial; one whose subscription lapsed is created
    already expired, because their free period is long spent and re-granting
    it here would hand a fresh trial to every dormant account at once.
    """
    plan = Plan()

    for row in db_rows:
        user_id = str(row.get("id") or "")
        if not user_id:
            plan.skipped.append(("<no id>", "row has no id"))
            continue
        if row.get("merged_into"):
            plan.skipped.append((user_id, "account was merged into another"))
            continue

        stored_uuid = row.get("remnawave_uuid")
        if stored_uuid and str(stored_uuid) in panel_uuids:
            plan.already_have.append(user_id)
            continue

        username = panel_username_for(user_id)
        telegram_id = row.get("telegram_id")
        candidates = [
            row.get("remnawave_username"),
            username,
            str(telegram_id) if telegram_id is not None else None,
        ]
        if any(name and name in panel_usernames for name in candidates):
            plan.already_have.append(user_id)
            continue

        subscription_ends = int(row.get("subscription_ends") or 0)
        if subscription_ends <= 0:
            # Never had anything: this is a first account, so it gets the
            # trial. `subscription_ends` moving off zero is what stops the
            # same user being granted one again on a later run.
            plan.to_create.append(
                Provision(
                    user_id=user_id,
                    telegram_id=telegram_id,
                    username=username,
                    expire_ts=now + trial_days * 86400,
                    trial_days=trial_days,
                    create=True,
                    reason="new account",
                )
            )
            continue

        plan.to_create.append(
            Provision(
                user_id=user_id,
                telegram_id=telegram_id,
                username=username,
                expire_ts=subscription_ends,
                create=True,
                reason="restoring an existing subscription"
                if subscription_ends > now
                else "restoring a lapsed account",
            )
        )

    return plan

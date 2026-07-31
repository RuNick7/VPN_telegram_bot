"""
Which squad a user belongs in, shared by both bots.

There are exactly three, and none of them is about capacity: **paid**, **FREE**
and **LTE** describe what a person is entitled to, not which server they land
on. Load is spread by balancers in front of the nodes, which is not this
codebase's business.

It used to be. Paid users were distributed across `internal-1`, `internal-2`,
... created on demand once each filled up, and that brought a workaround with
it -- a detached task that re-read up to 200 users five seconds after creating
a squad, to evict whoever the panel had swept in. All of that is gone: there
is one paid squad, its name is configured, and nothing here creates squads at
all. An operator manages them in the panel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .remnawave import RemnawaveClient

logger = logging.getLogger(__name__)


class SquadResolutionError(Exception):
    """A configured squad name does not exist in the panel."""


def members_count(squad: dict[str, Any]) -> int:
    """Members in a squad, or 0 when the panel omits the count."""
    count = (squad.get("info") or {}).get("membersCount")
    return int(count) if isinstance(count, int) else 0


@dataclass(frozen=True)
class SquadRoles:
    """
    Which squad UUID plays which role, resolved once from configured names.

    Resolving up front and passing this around is the point: `legacy-main`
    re-derived roles by string-matching squad names on every call, so renaming
    a squad in the panel UI silently changed who counted as paid -- with no
    error anywhere. Here a bad name fails at resolution time, loudly, and
    everything downstream works with UUIDs that cannot drift.
    """

    free_uuid: str
    lte_uuid: str | None
    paid_uuid: str

    def tier_of(self, squad_uuids: list[str] | set[str]) -> str:
        """
        Classify a user's current squad membership.

        "paid" wins over "free" when both are present: that combination is a
        half-applied transition, and treating it as paid means the next
        reconciliation cleans it up rather than cutting the user off.
        """
        current = set(squad_uuids)
        if self.paid_uuid in current:
            return "paid"
        if self.free_uuid in current:
            return "free"
        return "unknown"

    def strip_managed(self, squad_uuids: list[str]) -> list[str]:
        """
        Drop every squad this module owns, preserving anything else.

        Squads an operator added by hand are none of our business, so
        reconciliation edits only the memberships it is responsible for.
        """
        managed = {self.free_uuid, self.paid_uuid}
        if self.lte_uuid:
            managed.add(self.lte_uuid)
        return [uuid for uuid in squad_uuids if uuid not in managed]


def _find_by_name(squads: list[dict[str, Any]], name: str) -> str | None:
    needle = name.strip().lower()
    for squad in squads:
        if str(squad.get("name") or "").strip().lower() == needle and squad.get("uuid"):
            return str(squad["uuid"])
    return None


async def resolve_squad_roles(
    client: RemnawaveClient,
    *,
    free_name: str,
    lte_name: str | None,
    paid_name: str,
) -> SquadRoles:
    """
    Map configured squad names onto panel UUIDs, or raise.

    A missing FREE or paid squad raises `SquadResolutionError`, because
    neither failure is survivable quietly. Without FREE there is nowhere to
    demote expired users to, so everyone would keep paid access. Without the
    paid squad nobody can be promoted after paying -- customers would be
    charged and get nothing, and the only symptom would be silence.

    Failing the whole run also stops demotions for as long as the name is
    wrong. That is deliberate: a loud outage an operator fixes in a minute
    beats a half-working reconciliation nobody notices for a week.

    A missing LTE squad is tolerated -- that feature is optional, and its
    monitor simply does nothing.
    """
    squads = await client.list_internal_squads()

    def available() -> str:
        return ", ".join(sorted(str(s.get("name") or "?") for s in squads)) or "(none)"

    free_uuid = _find_by_name(squads, free_name)
    if not free_uuid:
        raise SquadResolutionError(
            f"FREE squad {free_name!r} not found in the panel. Available squads: {available()}. "
            f"Create it, or fix FREE_SQUAD_NAME."
        )

    paid_uuid = _find_by_name(squads, paid_name)
    if not paid_uuid:
        raise SquadResolutionError(
            f"Paid squad {paid_name!r} not found in the panel. Available squads: {available()}. "
            f"Create it, or fix PAID_SQUAD_NAME."
        )

    lte_uuid = _find_by_name(squads, lte_name) if lte_name else None
    if lte_name and not lte_uuid:
        logger.warning(
            "LTE squad %r not found in the panel; LTE quota enforcement will stay idle", lte_name
        )

    logger.info(
        "Resolved squads: paid=%s free=%s lte=%s", paid_uuid, free_uuid, lte_uuid or "-"
    )
    return SquadRoles(free_uuid=free_uuid, lte_uuid=lte_uuid, paid_uuid=paid_uuid)


async def resolve_paid_squad_uuid(client: RemnawaveClient, paid_name: str) -> str | None:
    """
    Just the paid squad, for the paths that only need somewhere to put a user.

    Returns None rather than raising: account creation should not fail because
    squad placement did. A user with no squad still exists and still has a
    link; the reconciliation job puts them right on its next pass.
    """
    squad_uuid = _find_by_name(await client.list_internal_squads(), paid_name)
    if not squad_uuid:
        logger.error(
            "Paid squad %r not found in the panel; user left unassigned until reconciliation",
            paid_name,
        )
    return squad_uuid

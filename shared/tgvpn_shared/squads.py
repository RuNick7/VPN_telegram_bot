"""
Internal-squad placement logic, shared by both bots.

Remnawave caps how many users one internal squad should hold, so new users are
spread across `internal-1`, `internal-2`, ... squads created on demand. Both
bots implemented this same walk independently (admin_bot in
`app/services/users.py`, user_bot in `app/services/remnawave/vpn_service.py`),
including the same "normalize members after creating a squad" workaround.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from .remnawave import RemnawaveClient

logger = logging.getLogger(__name__)

# How long to wait before reconciling a freshly created squad's membership.
# Remnawave assigns new users to squads asynchronously on its side, so reading
# back immediately returns a stale picture.
_NORMALIZE_DELAY_SECONDS = 5.0


class SquadResolutionError(Exception):
    """A configured squad name does not exist in the panel."""


def members_count(squad: dict[str, Any]) -> int:
    """Members in a squad, or 0 when the panel omits the count."""
    count = (squad.get("info") or {}).get("membersCount")
    return int(count) if isinstance(count, int) else 0


def extract_inbound_ids(squad: dict[str, Any] | None) -> list[str]:
    """UUIDs of a squad's inbounds -- used as the template for a new squad."""
    if not squad:
        return []
    return [str(inbound["uuid"]) for inbound in (squad.get("inbounds") or []) if inbound.get("uuid")]


def next_internal_squad_name(prefix: str, squads: list[dict[str, Any]]) -> str:
    """`internal-4` given existing `internal-1..3`; numbering starts at 1."""
    max_index = 0
    for squad in squads:
        name = str(squad.get("name") or "")
        if not name.startswith(f"{prefix}-"):
            continue
        suffix = name[len(prefix) + 1:]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return f"{prefix}-{max_index + 1}"


async def get_or_create_internal_squad(
    client: RemnawaveClient,
    *,
    max_users: int,
    prefix: str,
) -> tuple[dict[str, Any] | None, bool]:
    """
    Return `(squad, was_created)` -- the first squad with room, else a new one.

    A newly created squad copies its inbounds from any existing squad that has
    some, so it carries the same connectivity as the rest.
    """
    squads = await client.list_internal_squads()
    for squad in squads:
        if members_count(squad) < max_users:
            return squad, False

    name = next_internal_squad_name(prefix, squads)
    template = next((s for s in squads if (s.get("inbounds") or [])), None)
    inbound_ids = extract_inbound_ids(template)
    logger.info("Creating internal squad %s with %s inbounds", name, len(inbound_ids))
    return await client.create_internal_squad(name, inbound_ids), True


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
    paid_uuids: frozenset[str]

    def tier_of(self, squad_uuids: list[str] | set[str]) -> str:
        """
        Classify a user's current squad membership.

        "paid" wins over "free" when both are present: that combination is a
        half-applied transition, and treating it as paid means the next
        reconciliation cleans it up rather than cutting the user off.
        """
        current = set(squad_uuids)
        if current & self.paid_uuids:
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
        managed = {self.free_uuid, *self.paid_uuids}
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
    paid_prefix: str,
) -> SquadRoles:
    """
    Map configured squad names onto panel UUIDs, or raise.

    Raises `SquadResolutionError` when the FREE squad is missing, because
    without it there is nowhere to demote expired users to -- and quietly
    skipping demotion would leave everyone with paid access, the exact silent
    failure this phase exists to prevent. A missing LTE squad is tolerated:
    that feature is optional, and its monitor simply does nothing.
    """
    squads = await client.list_internal_squads()

    free_uuid = _find_by_name(squads, free_name)
    if not free_uuid:
        available = ", ".join(sorted(str(s.get("name") or "?") for s in squads)) or "(none)"
        raise SquadResolutionError(
            f"FREE squad {free_name!r} not found in the panel. Available squads: {available}. "
            f"Create it, or fix FREE_SQUAD_NAME."
        )

    lte_uuid = _find_by_name(squads, lte_name) if lte_name else None
    if lte_name and not lte_uuid:
        logger.warning(
            "LTE squad %r not found in the panel; LTE quota enforcement will stay idle", lte_name
        )

    prefix = paid_prefix.strip().lower()
    paid_uuids = {
        str(squad["uuid"])
        for squad in squads
        if squad.get("uuid")
        and str(squad.get("name") or "").strip().lower().startswith(f"{prefix}-")
    }
    if not paid_uuids:
        logger.warning(
            "No paid squads matching prefix %r; promotions will create the first one", paid_prefix
        )

    logger.info(
        "Resolved squads: free=%s lte=%s paid=%d", free_uuid, lte_uuid or "-", len(paid_uuids)
    )
    return SquadRoles(free_uuid=free_uuid, lte_uuid=lte_uuid, paid_uuids=frozenset(paid_uuids))


async def normalize_new_squad_members(
    client: RemnawaveClient,
    squad_uuid: str,
    user_uuid: str,
    delay_seconds: float = _NORMALIZE_DELAY_SECONDS,
) -> None:
    """
    Make a just-created squad contain exactly `user_uuid` and nobody else.

    Creating a squad can sweep in other users on the panel's side, which would
    silently blow past the per-squad cap the numbering scheme exists to
    enforce. Runs detached (fire-and-forget) after squad creation, so failures
    are logged rather than raised.
    """
    await asyncio.sleep(delay_seconds)
    data = await client.list_users(page=1, size=200)
    for user in data.get("users") or []:
        uuid = user.get("uuid")
        if not uuid:
            continue
        current = [str(s["uuid"]) for s in (user.get("activeInternalSquads") or []) if s.get("uuid")]
        if str(uuid) == str(user_uuid):
            desired = [str(squad_uuid)]
        else:
            desired = [s for s in current if s != str(squad_uuid)]
        if desired == current:
            continue
        try:
            await client.set_user_squads([str(uuid)], desired)
            logger.info("Updated user %s squads -> %s", uuid, desired)
        except Exception as exc:
            logger.warning("Failed to update user %s squads: %s", uuid, exc)

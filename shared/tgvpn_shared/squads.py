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
from typing import Any

from .remnawave import RemnawaveClient

logger = logging.getLogger(__name__)

# How long to wait before reconciling a freshly created squad's membership.
# Remnawave assigns new users to squads asynchronously on its side, so reading
# back immediately returns a stale picture.
_NORMALIZE_DELAY_SECONDS = 5.0


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

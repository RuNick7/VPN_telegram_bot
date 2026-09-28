"""
Squad role resolution.

The failure this guards against is specific: `legacy-main` re-derived roles by
string-matching squad names on every call, so renaming a squad in the panel UI
silently changed who counted as paid, with no error anywhere.

There are three roles and no capacity anywhere in them -- paid, FREE and LTE
describe entitlement, not which server someone lands on. Distribution across
`internal-1..N` is gone; balancers in front of the nodes handle load.
"""

import pytest

from tgvpn_shared.squads import (
    SquadResolutionError,
    SquadRoles,
    resolve_paid_squad_uuid,
    resolve_squad_roles,
)


class FakeClient:
    def __init__(self, squads):
        self._squads = squads

    async def list_internal_squads(self):
        return self._squads


PANEL = [
    {"uuid": "free-1", "name": "FREE"},
    {"uuid": "lte-1", "name": "LTE"},
    {"uuid": "paid-1", "name": "internal"},
    {"uuid": "custom", "name": "vip-handpicked"},
]


async def resolve(squads=PANEL, *, free="FREE", lte="LTE", paid="internal"):
    return await resolve_squad_roles(
        FakeClient(squads), free_name=free, lte_name=lte, paid_name=paid
    )


async def test_roles_resolve_to_uuids():
    roles = await resolve()
    assert roles.free_uuid == "free-1"
    assert roles.lte_uuid == "lte-1"
    assert roles.paid_uuid == "paid-1"


async def test_squad_names_match_case_insensitively():
    """Panel operators type names by hand; case is not a meaningful difference."""
    roles = await resolve(free="free", lte="lte", paid="INTERNAL")
    assert roles.free_uuid == "free-1"
    assert roles.paid_uuid == "paid-1"


async def test_the_paid_squad_name_is_configurable():
    squads = [*PANEL, {"uuid": "other-1", "name": "subscribers"}]
    roles = await resolve(squads, paid="subscribers")
    assert roles.paid_uuid == "other-1"


async def test_a_name_must_match_exactly_not_by_prefix():
    """
    `internal-1` is no longer a paid squad just because it starts with the
    configured name -- the numbered series does not exist any more, and
    matching loosely would quietly pick up a leftover from before.
    """
    squads = [
        {"uuid": "free-1", "name": "FREE"},
        {"uuid": "old-1", "name": "internal-1"},
    ]
    with pytest.raises(SquadResolutionError):
        await resolve(squads)


async def test_missing_free_squad_raises_rather_than_degrading():
    """
    Without a FREE squad there is nowhere to demote expired users to.

    Continuing anyway would leave every lapsed subscription on paid squads --
    the exact silent failure this phase exists to prevent.
    """
    squads = [s for s in PANEL if s["name"] != "FREE"]
    with pytest.raises(SquadResolutionError) as excinfo:
        await resolve(squads)
    # The message has to be actionable: which name was looked for, and what
    # the panel actually offers.
    assert "FREE" in str(excinfo.value)
    assert "internal" in str(excinfo.value)


async def test_missing_paid_squad_raises_too():
    """
    Nobody could be promoted after paying. The customer is charged and gets
    nothing, and the only symptom is silence -- so this has to be loud, even
    though failing the run also pauses demotions until the name is fixed.
    """
    squads = [s for s in PANEL if s["name"] != "internal"]
    with pytest.raises(SquadResolutionError) as excinfo:
        await resolve(squads)
    assert "PAID_SQUAD_NAME" in str(excinfo.value)


async def test_missing_lte_squad_is_tolerated():
    """LTE is optional; its absence just leaves quota enforcement idle."""
    squads = [s for s in PANEL if s["name"] != "LTE"]
    roles = await resolve(squads)
    assert roles.lte_uuid is None
    assert roles.free_uuid == "free-1"


@pytest.mark.parametrize(
    "current, expected",
    [
        (["paid-1"], "paid"),
        (["free-1"], "free"),
        (["custom"], "unknown"),
        ([], "unknown"),
        # Both present means a half-applied transition. Calling it paid lets
        # the next pass clean up rather than cutting the user off mid-flight.
        (["paid-1", "free-1"], "paid"),
    ],
)
async def test_tier_classification(current, expected):
    roles = await resolve()
    assert roles.tier_of(current) == expected


async def test_strip_managed_preserves_squads_we_do_not_own():
    """A squad an operator added by hand is not ours to remove."""
    roles = await resolve()
    assert roles.strip_managed(["paid-1", "free-1", "lte-1", "custom"]) == ["custom"]


def test_squad_roles_is_hashable_and_immutable():
    """Resolved once at startup and passed around; it must not be mutated."""
    roles = SquadRoles(free_uuid="f", lte_uuid=None, paid_uuid="p")
    with pytest.raises(Exception):
        roles.free_uuid = "other"  # type: ignore[misc]


# -- the lightweight lookup ------------------------------------------------


async def test_the_paid_squad_can_be_looked_up_on_its_own():
    """Account creation only needs somewhere to put the user."""
    assert await resolve_paid_squad_uuid(FakeClient(PANEL), "internal") == "paid-1"


async def test_a_missing_paid_squad_returns_none_rather_than_raising_there():
    """
    Creation must not fail because placement did. A user with no squad still
    exists and still has a link, and the reconciliation job puts them right on
    its next pass -- refusing to create the account would be worse.
    """
    assert await resolve_paid_squad_uuid(FakeClient([]), "internal") is None

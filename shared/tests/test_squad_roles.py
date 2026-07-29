"""
Squad role resolution.

The failure this guards against is specific: `legacy-main` re-derived roles by
string-matching squad names on every call, so renaming a squad in the panel UI
silently changed who counted as paid, with no error anywhere.
"""

import pytest

from tgvpn_shared.squads import SquadResolutionError, SquadRoles, resolve_squad_roles


class FakeClient:
    def __init__(self, squads):
        self._squads = squads

    async def list_internal_squads(self):
        return self._squads


PANEL = [
    {"uuid": "free-1", "name": "FREE"},
    {"uuid": "lte-1", "name": "LTE"},
    {"uuid": "int-1", "name": "internal-1"},
    {"uuid": "int-2", "name": "internal-2"},
    {"uuid": "custom", "name": "vip-handpicked"},
]


async def resolve(squads=PANEL, *, free="FREE", lte="LTE", prefix="internal"):
    return await resolve_squad_roles(
        FakeClient(squads), free_name=free, lte_name=lte, paid_prefix=prefix
    )


async def test_roles_resolve_to_uuids():
    roles = await resolve()
    assert roles.free_uuid == "free-1"
    assert roles.lte_uuid == "lte-1"
    assert roles.paid_uuids == frozenset({"int-1", "int-2"})


async def test_squad_names_match_case_insensitively():
    """Panel operators type names by hand; case is not a meaningful difference."""
    roles = await resolve(free="free", lte="lte")
    assert roles.free_uuid == "free-1"
    assert roles.lte_uuid == "lte-1"


async def test_missing_free_squad_raises_rather_than_degrading():
    """
    Without a FREE squad there is nowhere to demote expired users to.

    Continuing anyway would leave every lapsed subscription on paid squads --
    the exact silent failure this phase exists to prevent -- so this must be
    an error, not a warning.
    """
    squads = [s for s in PANEL if s["name"] != "FREE"]
    with pytest.raises(SquadResolutionError) as excinfo:
        await resolve(squads)
    # The message has to be actionable: which name was looked for, and what
    # the panel actually offers.
    assert "FREE" in str(excinfo.value)
    assert "internal-1" in str(excinfo.value)


async def test_missing_lte_squad_is_tolerated():
    """LTE is optional; its absence just leaves quota enforcement idle."""
    squads = [s for s in PANEL if s["name"] != "LTE"]
    roles = await resolve(squads)
    assert roles.lte_uuid is None
    assert roles.free_uuid == "free-1"


async def test_no_paid_squads_is_tolerated():
    """A fresh panel has none yet; the first promotion creates one."""
    roles = await resolve([{"uuid": "free-1", "name": "FREE"}])
    assert roles.paid_uuids == frozenset()


async def test_prefix_match_requires_the_separator():
    """`internalX` must not count as a paid pool just because it starts right."""
    squads = [{"uuid": "free-1", "name": "FREE"}, {"uuid": "x", "name": "internalX"}]
    roles = await resolve(squads)
    assert roles.paid_uuids == frozenset()


@pytest.mark.parametrize(
    "current, expected",
    [
        (["int-1"], "paid"),
        (["free-1"], "free"),
        (["custom"], "unknown"),
        ([], "unknown"),
        # Both present means a half-applied transition. Calling it paid lets
        # the next pass clean up rather than cutting the user off mid-flight.
        (["int-1", "free-1"], "paid"),
    ],
)
async def test_tier_classification(current, expected):
    roles = await resolve()
    assert roles.tier_of(current) == expected


async def test_strip_managed_preserves_squads_we_do_not_own():
    """A squad an operator added by hand is not ours to remove."""
    roles = await resolve()
    assert roles.strip_managed(["int-1", "free-1", "lte-1", "custom"]) == ["custom"]


def test_squad_roles_is_hashable_and_immutable():
    """Resolved once at startup and passed around; it must not be mutated."""
    roles = SquadRoles(free_uuid="f", lte_uuid=None, paid_uuids=frozenset({"p"}))
    with pytest.raises(Exception):
        roles.free_uuid = "other"  # type: ignore[misc]

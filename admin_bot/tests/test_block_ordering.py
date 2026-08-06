"""
What the node is left holding after a block.

There is no per-user disconnect on this panel, so a session is dropped by
disabling the account and enabling it straight back -- and `enable` means "put
this account into its node's inbounds". Whichever call touches the node last
therefore decides what the node holds, and it has to be ours.

Two shipped versions got this wrong in different ways and failed identically.
One stripped the squad and then dropped the session; the other stripped it
midway through the drop. Both ended on `enable`, and both handed access back:
eleven minutes after a block, a fresh connection was accepted and passed
traffic through the metered node the user was no longer entitled to.

So the membership change goes last, always. The drop is attempted first and is
allowed to fail -- a session that outlives its block is a smaller problem than
a block that never happened.
"""

import pytest
from tgvpn_shared.squads import SquadRoles

from app.scheduler.jobs.lte_traffic_monitor import _apply_squad

ROLES = SquadRoles(free_uuid="free-1", lte_uuid="lte-1", paid_uuid="int-1")


class RecordingPanel:
    """Records the order of the calls that reach the panel."""

    def __init__(self, *, drop_fails: bool = False):
        self.drop_fails = drop_fails
        self.calls: list[str] = []
        self.squads: list[list[str]] = []

    async def disconnect_user(self, user_uuid: str) -> bool:
        self.calls.append("disconnect")
        return not self.drop_fails

    async def set_user_squads(self, user_uuids: list[str], squad_uuids: list[str]):
        self.calls.append("squads")
        self.squads.append(list(squad_uuids))


@pytest.mark.asyncio
async def test_the_membership_change_is_the_last_thing_the_node_hears():
    panel = RecordingPanel()

    outcome = await _apply_squad(panel, ROLES, "104", ["int-1", "lte-1"], blocked=True)

    assert outcome == "blocked"
    assert panel.calls == ["disconnect", "squads"]
    assert panel.squads == [["int-1"]]


@pytest.mark.asyncio
async def test_a_block_lands_even_when_the_session_cannot_be_dropped():
    """The drop is best-effort. The block is not."""
    panel = RecordingPanel(drop_fails=True)

    assert await _apply_squad(panel, ROLES, "104", ["int-1", "lte-1"], blocked=True) == "blocked"
    assert panel.squads == [["int-1"]]


@pytest.mark.asyncio
async def test_squads_we_do_not_manage_survive_a_block():
    panel = RecordingPanel()

    await _apply_squad(panel, ROLES, "104", ["int-1", "lte-1", "vip"], blocked=True)
    assert panel.squads == [["int-1", "vip"]]


@pytest.mark.asyncio
async def test_unblocking_needs_no_drop():
    """Nothing to end: the point is to hand access back, not take it away."""
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["int-1"], blocked=False) == "unblocked"
    assert panel.calls == ["squads"]
    assert panel.squads == [["int-1", "lte-1"]]


@pytest.mark.asyncio
async def test_a_user_already_blocked_is_left_alone():
    """Idempotent: the monitor runs every few minutes on every user."""
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["int-1"], blocked=True) is None
    assert panel.calls == []


@pytest.mark.asyncio
async def test_lte_is_never_handed_to_someone_sitting_on_free():
    """
    The expiry monitor owns that state and would strip it again on its next
    pass, leaving the two jobs fighting each other every few minutes.
    """
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["free-1"], blocked=False) is None
    assert panel.calls == []

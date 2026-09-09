"""
What the node is left holding after a block.

A node is told what a user may reach only when the panel pushes it, and taking
somebody out of a squad is recorded *without* being pushed. Measured against a
live client: strip the LTE squad and the session ran on untouched for two
minutes; add `/connections/drop` and the socket died but the client, still
listed in the node's inbound, was back inside five seconds.

`disconnect_user` is what pushes -- it disables the account, drops the
sockets, and enables it again -- and the enable re-pushes whatever squads the
user holds *at that moment*. So the membership change goes first now, and the
cut second. Both orders were tried against the same live client; only this one
held, and the client reconnected within five seconds of the squad being handed
back, so the block was the block and not a broken client.

The cut is still allowed to fail. A session that outlives its block is a
smaller problem than a block that never happened.
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
        self.dropped_nodes: list[list[str]] = []

    async def disconnect_user(self, user_uuid: str, *, node_uuids=None) -> bool:
        self.calls.append("disconnect")
        self.dropped_nodes.append(list(node_uuids or []))
        return not self.drop_fails

    async def set_user_squads(self, user_uuids: list[str], squad_uuids: list[str]):
        self.calls.append("squads")
        self.squads.append(list(squad_uuids))


@pytest.mark.asyncio
async def test_the_membership_is_in_place_before_the_node_is_re_pushed():
    panel = RecordingPanel()

    outcome = await _apply_squad(panel, ROLES, "104", ["int-1", "lte-1"], blocked=True)

    assert outcome == "blocked"
    assert panel.calls == ["squads", "disconnect"]
    assert panel.squads == [["int-1"]]


@pytest.mark.asyncio
async def test_a_user_holding_nothing_but_lte_lands_on_free():
    """
    The panel rejects an empty squad list outright -- HTTP 500, errorCode A088
    -- so "take LTE away" cannot be spelled as "hold nothing". FREE is what no
    entitlement left means everywhere else here.
    """
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["lte-1"], blocked=True) == "blocked"
    assert panel.squads == [["free-1"]]


@pytest.mark.asyncio
async def test_only_the_metered_nodes_are_dropped():
    """
    The quota is spent on metered nodes. A subscriber who exhausts it still
    pays for the ordinary servers, and cutting those too would be a bug
    wearing an enforcement costume.
    """
    panel = RecordingPanel()

    await _apply_squad(
        panel, ROLES, "104", ["int-1", "lte-1"], blocked=True, nodes={"node-b", "node-a"}
    )
    assert panel.dropped_nodes == [["node-a", "node-b"]]


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
async def test_lte_is_granted_on_free_when_quota_allows():
    """
    LTE eligibility is about remaining balance, not paid-subscription status.
    The expiry monitor now preserves LTE membership through a demotion
    instead of stripping it, so there is no fight between the two jobs to
    guard against here any more.
    """
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["free-1"], blocked=False) == "unblocked"
    assert panel.squads == [["free-1", "lte-1"]]


@pytest.mark.asyncio
async def test_lte_is_withheld_from_an_unmanaged_account():
    """An account in neither FREE nor paid is not ours to touch."""
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["vip"], blocked=False) is None
    assert panel.calls == []


# -- drift -----------------------------------------------------------------
#
# A block looks applied when the membership is right, so an account the node
# is still holding is skipped every pass, forever. Traffic moving on a metered
# node is the evidence, and it is already fetched.


@pytest.mark.asyncio
async def test_a_blocked_user_still_passing_traffic_is_cut_again():
    panel = RecordingPanel()

    outcome = await _apply_squad(
        panel, ROLES, "104", ["int-1"], blocked=True, nodes={"node-a"}, still_flowing=True
    )

    assert outcome == "recut"
    assert panel.calls == ["disconnect"]
    assert panel.dropped_nodes == [["node-a"]]


@pytest.mark.asyncio
async def test_a_recut_does_not_touch_membership():
    """It is already right. Re-sending it would be a write with nothing to say."""
    panel = RecordingPanel()

    await _apply_squad(panel, ROLES, "104", ["int-1"], blocked=True, still_flowing=True)
    assert panel.squads == []


@pytest.mark.asyncio
async def test_a_quiet_blocked_user_costs_nothing():
    """The common case, every pass, for every blocked account."""
    panel = RecordingPanel()

    assert await _apply_squad(panel, ROLES, "104", ["int-1"], blocked=True) is None
    assert panel.calls == []

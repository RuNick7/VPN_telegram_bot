"""
Reading a usage figure out of the panel.

Both halves of this were broken at once, and each was enough on its own to
meter every user at zero for ever:

- the loop skipped any account without a `uuid`, and a newer panel names
  accounts with a numeric `id` and carries no `uuid` at all;
- the answer to the endpoint that *does* work is a chart -- `series`, one entry
  per node -- and the parser only knew flat `items`/`rows` shapes.

Neither failed loudly. The job recorded success on every pass while a user with
traffic in the panel showed a full allowance in the cabinet. So the payloads
below are copied from what `r.kairavpn.pro` actually returned, not invented:
the point is to fail when a panel upgrade changes the shape again.
"""

import pytest

from app.scheduler.jobs.lte_traffic_monitor import (
    fetch_usage_bytes,
    sum_metered,
    usage_by_node,
)

LTE_NODE = "f1d40775-8acb-4ce4-86ce-2ae6c09c6a57"
OTHER_NODE = "aaaaaaaa-0000-0000-0000-000000000000"

# GET /bandwidth-stats/users/104?start=2026-07-30&end=2026-08-06
CHART_PAYLOAD = {
    "categories": ["2026-08-04", "2026-08-05", "2026-08-06"],
    "series": [
        {
            "uuid": LTE_NODE,
            "name": "Netherlands 1-2 LTE",
            "color": "#9c6a57",
            "countryCode": "XX",
            "total": 126406,
            "data": [74663, 51743, 0],
        }
    ],
    "sparklineData": [74663, 51743, 0],
    "topNodes": [{"uuid": LTE_NODE, "name": "Netherlands 1-2 LTE", "total": 126406}],
}


# -- shapes ----------------------------------------------------------------


def test_a_chart_answer_is_read_per_node():
    assert usage_by_node(CHART_PAYLOAD) == [(LTE_NODE, 126406)]


def test_topnodes_does_not_double_the_reading():
    """
    `series` and `topNodes` carry the same figures.

    Reading both would charge every user twice for the same traffic, which is
    worse than reading neither.
    """
    assert sum(count for _, count in usage_by_node(CHART_PAYLOAD)) == 126406


def test_a_chart_with_no_traffic_reads_as_nothing():
    assert usage_by_node({"categories": ["2026-08-06"], "series": [], "topNodes": []}) == []


def test_topnodes_alone_is_still_read():
    """A panel version that omits `series` must not silently meter at zero."""
    payload = {"topNodes": [{"uuid": LTE_NODE, "total": 4096}]}
    assert usage_by_node(payload) == [(LTE_NODE, 4096)]


@pytest.mark.parametrize("key", ["items", "rows", "usage", "stats"])
def test_the_older_flat_shapes_still_work(key):
    payload = {key: [{"nodeUuid": LTE_NODE, "total": 2048}]}
    assert usage_by_node(payload) == [(LTE_NODE, 2048)]


def test_a_bare_list_is_a_flat_shape_too():
    assert usage_by_node([{"node_uuid": LTE_NODE, "totalDownload": 100, "totalUpload": 23}]) == [
        (LTE_NODE, 123)
    ]


def test_a_flat_row_that_names_no_node_stays_unattributed():
    """
    `uuid` on a flat usage row is not read as a node.

    In a chart series it always is one; in a usage row it may well be the user
    the row belongs to, and charging a quota against a misread identifier is
    worse than reading nothing.
    """
    assert usage_by_node({"items": [{"uuid": "some-user", "total": 999}]}) == [(None, 999)]


def test_an_answer_in_no_known_shape_reads_as_nothing():
    assert usage_by_node({"unexpected": True}) == []


# -- what counts against the quota -----------------------------------------


def test_only_metered_nodes_are_charged():
    """Traffic on ordinary servers is not what the LTE allowance is for."""
    rows = [(LTE_NODE, 126406), (OTHER_NODE, 9 * 1024**3)]
    assert sum_metered(rows, {LTE_NODE}) == 126406


def test_traffic_on_no_metered_node_costs_nothing():
    assert sum_metered([(OTHER_NODE, 5 * 1024**3)], {LTE_NODE}) == 0


def test_several_metered_nodes_add_up():
    rows = [(LTE_NODE, 100), (OTHER_NODE, 50)]
    assert sum_metered(rows, {LTE_NODE, OTHER_NODE}) == 150


def test_an_unattributed_total_is_counted_rather_than_lost():
    """
    A panel that reports one undifferentiated figure would otherwise meter at
    zero for ever -- silently, which is exactly how this was broken. The
    compromise is deliberate and the job logs it.
    """
    assert sum_metered([(None, 4096)], {LTE_NODE}) == 4096


def test_an_attributed_answer_does_not_fall_back():
    """
    Once anything is attributed, an unnamed row is not swept in on top.

    Otherwise a payload naming three nodes and totalling a fourth row would
    charge the same bytes twice.
    """
    assert sum_metered([(LTE_NODE, 100), (None, 900)], {LTE_NODE}) == 100


# -- end to end against a fake panel ---------------------------------------


class FakePanel:
    """Answers the endpoint the real panel answers, and 404s the rest."""

    def __init__(self, payload=CHART_PAYLOAD):
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def request(self, method, endpoint, params=None):
        self.calls.append((endpoint, params or {}))
        if not endpoint.startswith("/bandwidth-stats/users/") or endpoint.endswith("/legacy"):
            raise RuntimeError(f"Cannot GET /api{endpoint}")
        return {"response": self.payload}


@pytest.mark.asyncio
async def test_usage_is_read_for_a_numerically_named_account():
    """
    The whole failure, end to end: account `104`, 126 406 bytes in the panel,
    and a reading of zero before this was fixed.
    """
    panel = FakePanel()
    assert await fetch_usage_bytes(panel, "104", 1_754_000_000, 1_754_400_000, {LTE_NODE}) == 126406


@pytest.mark.asyncio
async def test_no_metered_nodes_means_nothing_is_read():
    """An empty node set is "nothing to enforce", never "meter everything"."""
    panel = FakePanel()
    assert await fetch_usage_bytes(panel, "104", 1_754_000_000, 1_754_400_000, set()) == 0
    assert panel.calls == []


@pytest.mark.asyncio
async def test_the_window_is_sent_as_dates():
    panel = FakePanel()
    await fetch_usage_bytes(panel, "104", 1_785_801_600, 1_785_974_400, {LTE_NODE})
    _, params = panel.calls[-1]
    assert params == {"start": "2026-08-04", "end": "2026-08-06"}


@pytest.mark.asyncio
async def test_every_endpoint_failing_raises_rather_than_reading_zero():
    """
    A reading of zero and an unreachable panel must not look the same: the
    first spends nothing, the second would hand out free metered traffic.
    """

    class DeadPanel:
        async def request(self, *args, **kwargs):
            raise RuntimeError("panel down")

    with pytest.raises(RuntimeError):
        await fetch_usage_bytes(DeadPanel(), "104", 0, 1, {LTE_NODE})

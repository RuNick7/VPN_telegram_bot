"""
LTE quota arithmetic.

`plan_quota` returns a *delta* rather than a recomputed balance, and that
shape is the whole defence against the bug `legacy-main` shipped: the monitor
reads state, makes slow panel calls, then writes back, and a purchase landing
in that window would be erased by an absolute write.
"""

import pytest

from app.scheduler.jobs.lte_traffic_monitor import plan_quota, resolve_lte_nodes, settle_cycle

GB = 1024**3


def plan(**kwargs):
    defaults = dict(
        usage_bytes=0,
        free_bytes=10 * GB,
        cycle_spent=0,
        paid_balance=0,
        subscription_active=True,
    )
    return plan_quota(**{**defaults, **kwargs})


def test_usage_within_the_free_allowance_costs_nothing():
    spend, cycle_spent, blocked = plan(usage_bytes=3 * GB)
    assert (spend, cycle_spent, blocked) == (0, 0, False)


def test_usage_exactly_at_the_allowance_is_still_free():
    assert plan(usage_bytes=10 * GB) == (0, 0, False)


def test_overage_is_charged_to_purchased_traffic():
    spend, cycle_spent, blocked = plan(usage_bytes=12 * GB, paid_balance=5 * GB)
    assert spend == 2 * GB
    assert cycle_spent == 2 * GB
    assert blocked is False


def test_overage_beyond_the_purchased_balance_blocks():
    spend, cycle_spent, blocked = plan(usage_bytes=20 * GB, paid_balance=3 * GB)
    assert spend == 3 * GB       # everything available was charged
    assert cycle_spent == 3 * GB
    assert blocked is True       # 7 GB still unpaid


def test_overage_with_no_balance_blocks_immediately():
    assert plan(usage_bytes=11 * GB, paid_balance=0) == (0, 0, True)


def test_already_charged_usage_is_not_charged_again():
    """
    The delta is what's *new* since last pass.

    Charging the full overage every five minutes would drain a user's balance
    in an hour for traffic they spent once.
    """
    spend, cycle_spent, blocked = plan(
        usage_bytes=12 * GB, cycle_spent=2 * GB, paid_balance=5 * GB
    )
    assert spend == 0
    assert cycle_spent == 2 * GB
    assert blocked is False


def test_further_usage_charges_only_the_increment():
    spend, cycle_spent, _ = plan(usage_bytes=15 * GB, cycle_spent=2 * GB, paid_balance=5 * GB)
    assert spend == 3 * GB
    assert cycle_spent == 5 * GB


def test_a_topup_between_passes_is_spendable_not_lost():
    """
    The scenario the delta shape exists for.

    First pass exhausts a 1 GB balance and blocks. The user buys 5 GB. The
    next pass sees the larger balance and only charges the still-unpaid
    remainder -- it does not re-charge, and does not overwrite the purchase.
    """
    spend_1, cycle_spent_1, blocked_1 = plan(usage_bytes=14 * GB, paid_balance=1 * GB)
    assert (spend_1, cycle_spent_1, blocked_1) == (1 * GB, 1 * GB, True)

    spend_2, cycle_spent_2, blocked_2 = plan(
        usage_bytes=14 * GB, cycle_spent=cycle_spent_1, paid_balance=5 * GB
    )
    assert spend_2 == 3 * GB          # only the outstanding 3 GB
    assert cycle_spent_2 == 4 * GB
    assert blocked_2 is False


def test_lapsed_subscription_blocks_even_with_traffic_left():
    """Free mode means free servers; metered ones are not among them."""
    spend, _, blocked = plan(usage_bytes=1 * GB, paid_balance=100 * GB, subscription_active=False)
    assert blocked is True
    assert spend == 0


def test_a_zero_free_allowance_charges_from_the_first_byte():
    spend, _, blocked = plan(usage_bytes=1 * GB, free_bytes=0, paid_balance=2 * GB)
    assert spend == 1 * GB
    assert blocked is False


# -- cycle rollover --------------------------------------------------------

DAY = 86400
CYCLE = 30 * DAY


def test_cycle_does_not_roll_before_it_ends():
    start = 1_000_000
    assert settle_cycle(
        now=start + 10 * DAY, cycle_start=start, cycle_seconds=CYCLE, cycle_spent=5
    ) == (start, 5)


def test_rollover_resets_spend_but_advances_the_window():
    start = 1_000_000
    new_start, spent = settle_cycle(
        now=start + CYCLE + DAY, cycle_start=start, cycle_seconds=CYCLE, cycle_spent=5
    )
    assert new_start == start + CYCLE
    assert spent == 0


def test_many_missed_cycles_are_skipped_in_one_step():
    """
    A user the monitor hasn't seen in months must land on the current window
    immediately, not advance one cycle per pass.
    """
    start = 1_000_000
    new_start, spent = settle_cycle(
        now=start + 5 * CYCLE + DAY, cycle_start=start, cycle_seconds=CYCLE, cycle_spent=99
    )
    assert new_start == start + 5 * CYCLE
    assert spent == 0


def test_rollover_is_a_no_op_for_a_nonsensical_cycle_length():
    start = 1_000_000
    assert settle_cycle(now=start + DAY, cycle_start=start, cycle_seconds=0, cycle_spent=7) == (
        start,
        7,
    )


# -- node selection --------------------------------------------------------

NODES = [
    {"uuid": "n1", "name": "LTE-Moscow"},
    {"uuid": "n2", "name": "Fiber-Berlin"},
    {"uuid": "n3", "name": "lte-spare"},
]


def test_explicit_uuids_win_over_name_matching(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(type(settings), "lte_node_uuids", property(lambda self: ["n2"]))
    assert resolve_lte_nodes(NODES) == {"n2"}


def test_nodes_are_matched_by_name_substring(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(type(settings), "lte_node_uuids", property(lambda self: []))
    monkeypatch.setattr(type(settings), "lte_node_name_keywords", property(lambda self: ["lte"]))
    assert resolve_lte_nodes(NODES) == {"n1", "n3"}


def test_no_configuration_meters_nothing(monkeypatch):
    """
    An empty result must mean "nothing is metered", never "meter everything" --
    the latter would block every user the moment configuration went missing.
    """
    from app.config.settings import settings

    monkeypatch.setattr(type(settings), "lte_node_uuids", property(lambda self: []))
    monkeypatch.setattr(type(settings), "lte_node_name_keywords", property(lambda self: []))
    assert resolve_lte_nodes(NODES) == set()

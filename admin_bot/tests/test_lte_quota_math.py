"""
LTE quota arithmetic.

`plan_quota` returns a *delta* rather than a recomputed balance, and that
shape is the whole defence against the bug `legacy-main` shipped: the monitor
reads state, makes slow panel calls, then writes back, and a purchase landing
in that window would be erased by an absolute write.
"""

import pytest

from app.scheduler.jobs.lte_traffic_monitor import resolve_lte_nodes
from tgvpn_shared.lte_quota import format_traffic, plan_quota, remaining_now, settle_cycle

GB = 1024**3
MB = 1024**2


def plan(**kwargs):
    defaults = dict(
        usage_bytes=0,
        free_bytes=10 * GB,
        cycle_spent=0,
        paid_balance=0,
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


def test_a_lapsed_subscription_does_not_block_while_traffic_remains():
    """
    LTE eligibility is about balance, not paid-subscription status -- the
    expiry monitor decides whether LTE membership is worth keeping through a
    demotion; this only ever decides whether the quota itself is exhausted.
    """
    spend, _, blocked = plan(usage_bytes=1 * GB, paid_balance=100 * GB)
    assert blocked is False
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


# -- balance shown in menus ------------------------------------------------
#
# `remaining_now` reads stored state only -- no panel call -- because it backs
# a menu, not enforcement. `plan_quota` above remains the only thing that
# decides access.

NOW = 2_000_000


def state(**kwargs) -> dict:
    defaults = dict(
        lte_last_usage_bytes=0,
        lte_cycle_start=NOW - DAY,
        lte_paid_balance_bytes=0,
        lte_free_gb_override=None,
    )
    return {**defaults, **kwargs}


def remaining(**kwargs) -> int:
    return remaining_now(
        state=state(**kwargs), global_free_gb=10, cycle_seconds=CYCLE, now=NOW
    )


def test_an_untouched_allowance_is_fully_available():
    assert remaining() == 10 * GB


def test_usage_is_deducted_from_the_allowance():
    assert remaining(lte_last_usage_bytes=4 * GB) == 6 * GB


def test_purchased_traffic_adds_to_what_is_left():
    assert remaining(lte_last_usage_bytes=4 * GB, lte_paid_balance_bytes=3 * GB) == 9 * GB


def test_usage_past_the_allowance_leaves_only_purchased_traffic():
    assert remaining(lte_last_usage_bytes=14 * GB, lte_paid_balance_bytes=3 * GB) == 3 * GB


def test_a_personal_allowance_overrides_the_global_one():
    assert remaining(lte_free_gb_override=2) == 2 * GB


def test_a_zero_override_is_a_real_value_not_a_missing_one():
    """`0` means no free traffic; only `None` falls back to the global setting."""
    assert remaining(lte_free_gb_override=0) == 0


def test_a_rolled_cycle_shows_a_fresh_allowance_not_last_cycles_usage():
    """
    The correction this function exists for.

    A usage reading only means anything inside the window it was taken in.
    Between a rollover and the monitor's next pass the stored reading belongs
    to the previous cycle -- quoting it would tell a user with a full new
    allowance that they have nothing left.
    """
    assert (
        remaining_now(
            state=state(lte_last_usage_bytes=10 * GB, lte_cycle_start=NOW - 2 * CYCLE),
            global_free_gb=10,
            cycle_seconds=CYCLE,
            now=NOW,
        )
        == 10 * GB
    )


def test_usage_within_the_current_cycle_is_still_counted():
    """The rollover correction must not swallow legitimate in-window usage."""
    assert (
        remaining_now(
            state=state(lte_last_usage_bytes=10 * GB, lte_cycle_start=NOW - CYCLE + DAY),
            global_free_gb=10,
            cycle_seconds=CYCLE,
            now=NOW,
        )
        == 0
    )


def test_a_user_whose_cycle_never_started_gets_the_full_allowance():
    """`lte_cycle_start` is NULL until the monitor first sees them."""
    assert remaining(lte_cycle_start=None) == 10 * GB


def test_missing_fields_read_as_zero_rather_than_raising():
    """A menu must render off a partially-populated row, not crash."""
    assert remaining_now(state={}, global_free_gb=1, cycle_seconds=CYCLE, now=NOW) == 1 * GB


# -- display formatting ----------------------------------------------------


@pytest.mark.parametrize(
    "byte_count, expected",
    [
        (0, "0 МБ"),
        (150 * MB, "150 МБ"),
        (1023 * MB, "1023 МБ"),
        (1 * GB, "1.0 ГБ"),
        (4 * GB + 700 * MB, "4.7 ГБ"),
        (30 * GB, "30.0 ГБ"),
    ],
)
def test_traffic_is_formatted_for_a_customer(byte_count, expected):
    assert format_traffic(byte_count) == expected


@pytest.mark.parametrize("byte_count, expected", [(126_406, "123 КБ"), (500 * 1024, "500 КБ")])
def test_a_reading_below_a_megabyte_is_shown_rather_than_rounded_away(byte_count, expected):
    """
    Why the kilobyte branch exists.

    126 406 bytes was the real figure sitting in the panel while the cabinet
    said the allowance was untouched -- and at megabyte precision a meter that
    works and one that does not look exactly the same.
    """
    assert format_traffic(byte_count) == expected


def test_a_negative_amount_never_reaches_a_user():
    assert format_traffic(-5) == "0 МБ"


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

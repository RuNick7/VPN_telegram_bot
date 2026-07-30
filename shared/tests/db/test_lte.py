"""
LTE balance accounting against a real database.

The central guarantee: a purchase landing while the traffic monitor is mid-pass
survives. `legacy-main` lost those purchases by writing back an absolute
balance read before the panel calls.
"""

import asyncio

from tgvpn_shared.db import LteRepository, UserRepository

lte = LteRepository()
users = UserRepository()

GB = 1024**3


async def make_user(telegram_id: int = 1) -> int:
    await users.insert_subscription_user(telegram_id=telegram_id, subscription_ends=0)
    return telegram_id


async def test_new_user_starts_with_no_balance_and_no_cycle():
    tg = await make_user()
    state = await lte.get_state(tg)
    assert state["lte_paid_balance_bytes"] == 0
    assert state["lte_cycle_start"] is None
    assert state["squad_tier"] == "unknown"


async def test_state_of_a_missing_user_is_none():
    assert await lte.get_state(999_999) is None


async def test_first_cycle_is_assigned_once_and_then_left_alone():
    tg = await make_user()
    first = await lte.start_cycle_if_unset(tg, 1_000_000)
    assert first["lte_cycle_start"] == 1_000_000

    again = await lte.start_cycle_if_unset(tg, 2_000_000)
    assert again["lte_cycle_start"] == 1_000_000


async def test_rolling_the_cycle_resets_spend_but_keeps_bought_traffic():
    """Purchased traffic belongs to the user, not to a cycle."""
    tg = await make_user()
    await lte.start_cycle_if_unset(tg, 1_000_000)
    await lte.credit_balance(tg, 5 * GB)
    await lte.consume_balance(
        tg, spent_delta_bytes=0, cycle_spent_bytes=3 * GB, blocked=False, last_usage_bytes=0
    )

    await lte.roll_cycle(tg, 2_000_000)

    state = await lte.get_state(tg)
    assert state["lte_cycle_start"] == 2_000_000
    assert state["lte_cycle_spent_bytes"] == 0
    assert state["lte_paid_balance_bytes"] == 5 * GB


async def test_credit_adds_to_the_balance():
    tg = await make_user()
    assert await lte.credit_balance(tg, 2 * GB) == 2 * GB
    assert await lte.credit_balance(tg, 3 * GB) == 5 * GB


async def test_consume_subtracts_only_the_delta():
    tg = await make_user()
    await lte.credit_balance(tg, 10 * GB)

    result = await lte.consume_balance(
        tg, spent_delta_bytes=4 * GB, cycle_spent_bytes=4 * GB, blocked=False, last_usage_bytes=14 * GB
    )
    assert result["lte_paid_balance_bytes"] == 6 * GB
    assert result["lte_cycle_spent_bytes"] == 4 * GB
    assert result["lte_last_usage_bytes"] == 14 * GB
    assert result["lte_blocked"] is False


async def test_a_topup_during_a_monitor_pass_is_not_lost():
    """
    The regression this repository is shaped around.

    The monitor reads a 1 GB balance, then makes slow panel calls; the user
    buys 5 GB in that window; the monitor writes back what it spent. The
    purchase must still be there.
    """
    tg = await make_user()
    await lte.credit_balance(tg, 1 * GB)

    observed_balance = (await lte.get_state(tg))["lte_paid_balance_bytes"]
    assert observed_balance == 1 * GB

    await lte.credit_balance(tg, 5 * GB)  # purchase lands mid-pass

    await lte.consume_balance(
        tg, spent_delta_bytes=1 * GB, cycle_spent_bytes=1 * GB, blocked=True, last_usage_bytes=11 * GB
    )

    # 1 + 5 - 1 spent = 5. An absolute write of "observed minus spent" would
    # have left 0 and destroyed the purchase.
    assert (await lte.get_state(tg))["lte_paid_balance_bytes"] == 5 * GB


async def test_balance_never_goes_negative():
    tg = await make_user()
    await lte.credit_balance(tg, 1 * GB)
    result = await lte.consume_balance(
        tg, spent_delta_bytes=99 * GB, cycle_spent_bytes=0, blocked=True, last_usage_bytes=0
    )
    assert result["lte_paid_balance_bytes"] == 0


async def test_concurrent_credits_all_land():
    tg = await make_user()
    await asyncio.gather(*(lte.credit_balance(tg, 1 * GB) for _ in range(10)))
    assert (await lte.get_state(tg))["lte_paid_balance_bytes"] == 10 * GB


async def test_writes_to_a_missing_user_report_failure():
    assert await lte.credit_balance(999_999, GB) is None
    assert await lte.roll_cycle(999_999, 1) is None
    assert (
        await lte.consume_balance(
            999_999, spent_delta_bytes=0, cycle_spent_bytes=0, blocked=False, last_usage_bytes=0
        )
        is None
    )


async def test_bought_traffic_survives_a_cycle_rollover_end_to_end():
    """
    Purchased gigabytes carry over; only the free allowance resets.

    Walks two full cycles the way the monitor does -- settle the window, spend
    against it, write back -- rather than testing `roll_cycle` alone, since the
    guarantee only holds if no step in that sequence clears the balance.
    """
    from tgvpn_shared.lte_quota import plan_quota, settle_cycle

    tg = await make_user()
    cycle_seconds = 30 * 86400
    free_bytes = 10 * GB
    start = 1_000_000

    await lte.start_cycle_if_unset(tg, start)
    await lte.credit_balance(tg, 20 * GB)

    # --- cycle 1: burn the free allowance plus 5 GB of purchased traffic ---
    now = start + 10 * 86400
    state = await lte.get_state(tg)
    cycle_start, cycle_spent = settle_cycle(
        now=now,
        cycle_start=int(state["lte_cycle_start"]),
        cycle_seconds=cycle_seconds,
        cycle_spent=int(state["lte_cycle_spent_bytes"]),
    )
    assert cycle_start == start  # not rolled yet

    delta, cycle_spent, blocked = plan_quota(
        usage_bytes=15 * GB,
        free_bytes=free_bytes,
        cycle_spent=cycle_spent,
        paid_balance=int(state["lte_paid_balance_bytes"]),
        subscription_active=True,
    )
    await lte.consume_balance(
        tg, spent_delta_bytes=delta, cycle_spent_bytes=cycle_spent, blocked=blocked,
        last_usage_bytes=15 * GB,
    )
    assert (await lte.get_state(tg))["lte_paid_balance_bytes"] == 15 * GB

    # --- cycle 2: a month later, the window rolls ---
    now = start + cycle_seconds + 86400
    state = await lte.get_state(tg)
    cycle_start, cycle_spent = settle_cycle(
        now=now,
        cycle_start=int(state["lte_cycle_start"]),
        cycle_seconds=cycle_seconds,
        cycle_spent=int(state["lte_cycle_spent_bytes"]),
    )
    assert cycle_start == start + cycle_seconds
    assert cycle_spent == 0  # the free allowance is fresh again
    await lte.roll_cycle(tg, cycle_start)

    rolled = await lte.get_state(tg)
    # The whole point: the 15 GB bought last month is still there.
    assert rolled["lte_paid_balance_bytes"] == 15 * GB
    assert rolled["lte_cycle_spent_bytes"] == 0


async def test_bought_traffic_survives_many_idle_months():
    """A user who buys traffic and disappears still has it when they return."""
    tg = await make_user()
    await lte.start_cycle_if_unset(tg, 1_000_000)
    await lte.credit_balance(tg, 7 * GB)

    for month in range(1, 13):
        await lte.roll_cycle(tg, 1_000_000 + month * 30 * 86400)

    assert (await lte.get_state(tg))["lte_paid_balance_bytes"] == 7 * GB


async def test_free_gb_override_defaults_to_none():
    """NULL means "use the global setting" -- distinct from a 0 override."""
    tg = await make_user()
    assert (await lte.get_state(tg))["lte_free_gb_override"] is None


async def test_free_gb_override_round_trips():
    tg = await make_user()
    assert await lte.set_free_gb_override(tg, 25) is True
    assert (await lte.get_state(tg))["lte_free_gb_override"] == 25


async def test_a_zero_override_is_stored_not_treated_as_unset():
    """0 is a real override: this user gets no free traffic at all."""
    tg = await make_user()
    await lte.set_free_gb_override(tg, 0)
    assert (await lte.get_state(tg))["lte_free_gb_override"] == 0


async def test_override_can_be_cleared_back_to_the_global_setting():
    tg = await make_user()
    await lte.set_free_gb_override(tg, 25)
    await lte.set_free_gb_override(tg, None)
    assert (await lte.get_state(tg))["lte_free_gb_override"] is None


async def test_a_negative_override_is_clamped():
    tg = await make_user()
    await lte.set_free_gb_override(tg, -5)
    assert (await lte.get_state(tg))["lte_free_gb_override"] == 0


async def test_override_on_a_missing_user_reports_failure():
    assert await lte.set_free_gb_override(999_999, 5) is False


async def test_set_balance_is_absolute_unlike_credit():
    """The admin correcting a balance to a known figure, not applying a purchase."""
    tg = await make_user()
    await lte.credit_balance(tg, 10 * GB)
    assert await lte.set_balance(tg, 3 * GB) == 3 * GB


async def test_set_balance_can_zero_it_out():
    tg = await make_user()
    await lte.credit_balance(tg, 10 * GB)
    assert await lte.set_balance(tg, 0) == 0


async def test_set_balance_never_goes_negative():
    tg = await make_user()
    assert await lte.set_balance(tg, -5 * GB) == 0


async def test_set_balance_on_a_missing_user_reports_failure():
    assert await lte.set_balance(999_999, GB) is None


async def test_squad_tier_round_trips():
    tg = await make_user()
    await lte.set_squad_tier(tg, "free")
    assert (await lte.get_state(tg))["squad_tier"] == "free"
    await lte.set_squad_tier(tg, "paid")
    assert (await lte.get_state(tg))["squad_tier"] == "paid"


async def test_unknown_squad_tier_is_rejected():
    """The column has a CHECK constraint; catching it early gives a better error."""
    tg = await make_user()
    try:
        await lte.set_squad_tier(tg, "premium")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an unknown tier")


async def test_bulk_tier_update():
    for tg in (1, 2, 3):
        await make_user(tg)
    await lte.set_squad_tiers([1, 2], "free")
    assert (await lte.get_state(1))["squad_tier"] == "free"
    assert (await lte.get_state(3))["squad_tier"] == "unknown"


async def test_tier_counts_for_the_stats_screen():
    for tg in (1, 2, 3):
        await make_user(tg)
    await lte.set_squad_tiers([1, 2], "paid")
    await lte.set_squad_tiers([3], "free")
    assert await lte.get_tier_counts() == {"paid": 2, "free": 1}

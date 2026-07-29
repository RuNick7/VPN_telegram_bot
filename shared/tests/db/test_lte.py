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

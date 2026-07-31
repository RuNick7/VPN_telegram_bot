"""
Who the inactive-user cleanup picks, against a real database.

This job deletes panel accounts. Selecting one user too many takes away the
access of somebody who is paying; selecting one too few leaves the free
servers filling up, which is the whole reason it runs. Both directions are
tested here rather than reasoned about, because the rule lives in SQL and SQL
is where an `AND` binds differently than you expected.
"""

import time

from tgvpn_shared.db import LteRepository, UserRepository

users = UserRepository()
lte = LteRepository()

DAY = 86400
NOW = int(time.time())


async def make_user(
    telegram_id: int,
    *,
    days_ago: int | None = None,
    ends_in: int | None = None,
    tier: str = "free",
    panel_uuid: str | None = "11111111-1111-1111-1111-111111111111",
) -> dict:
    """A user whose subscription ended `days_ago` days ago, or ends in future."""
    if ends_in is not None:
        subscription_ends = NOW + ends_in * DAY
    elif days_ago is not None:
        subscription_ends = NOW - days_ago * DAY
    else:
        subscription_ends = 0

    await users.insert_subscription_user(
        telegram_id=telegram_id, subscription_ends=subscription_ends
    )
    row = await users.get_user_by_id(telegram_id)
    if panel_uuid:
        await users.set_panel_identity(
            str(row["id"]), remnawave_uuid=panel_uuid, remnawave_username=f"u-{telegram_id}"
        )
    await lte.set_squad_tier(telegram_id, tier)
    return dict(await users.get_user_by_id(telegram_id))


async def selected(*, free_tier: bool) -> set[int]:
    rows = await users.get_inactive_users_for_cleanup(30, free_tier_enabled=free_tier)
    return {row["telegram_id"] for row in rows}


# -- with the FREE tier on -------------------------------------------------


async def test_a_month_on_the_free_servers_is_selected():
    await make_user(1, days_ago=45, tier="free")
    assert await selected(free_tier=True) == {1}


async def test_someone_who_lapsed_last_week_is_left_alone():
    """The free tier is supposed to hold them; a week is not a month."""
    await make_user(1, days_ago=7, tier="free")
    assert await selected(free_tier=True) == set()


async def test_exactly_at_the_threshold_is_not_yet_selected():
    await make_user(1, days_ago=29, tier="free")
    assert await selected(free_tier=True) == set()


async def test_a_paying_user_is_never_selected():
    await make_user(1, ends_in=30, tier="paid")
    assert await selected(free_tier=True) == set()


async def test_a_long_lapsed_user_the_job_has_not_demoted_yet_is_left_alone():
    """
    'unknown' means the demotion job has not reached them. Deleting on the
    date alone would race the job that owns the squad -- and deleting somebody
    it was about to promote is not recoverable.
    """
    await make_user(1, days_ago=60, tier="unknown")
    assert await selected(free_tier=True) == set()


async def test_a_user_still_tagged_paid_is_left_alone():
    """
    Their date says lapsed but the job has not moved them. Same reasoning:
    the tag is the authority on which squad they are actually in.
    """
    await make_user(1, days_ago=60, tier="paid")
    assert await selected(free_tier=True) == set()


async def test_someone_who_never_had_a_subscription_is_not_selected():
    """Nothing in the panel to delete, and only noise in the report."""
    await make_user(1, tier="free")  # subscription_ends stays at epoch 0
    assert await selected(free_tier=True) == set()


async def test_a_merged_account_is_not_selected():
    """The survivor holds everything; the absorbed row owns no panel account."""
    await make_user(1, days_ago=60, tier="free")
    await make_user(2, days_ago=60, tier="free", panel_uuid=None)

    row_one = await users.get_user_by_id(1)
    row_two = await users.get_user_by_id(2)
    pool = await _pool()
    await pool.execute(
        "UPDATE users SET merged_into = $1::uuid WHERE id = $2::uuid",
        str(row_one["id"]), str(row_two["id"]),
    )

    assert await selected(free_tier=True) == {1}


# -- with the FREE tier off ------------------------------------------------


async def test_without_the_free_tier_the_tag_is_not_required():
    """
    Nothing writes a tier in that mode, so requiring one would disable the
    cleanup entirely.
    """
    await make_user(1, days_ago=45, tier="unknown")
    assert await selected(free_tier=False) == {1}


async def test_the_date_still_applies_without_the_free_tier():
    await make_user(1, days_ago=7, tier="unknown")
    assert await selected(free_tier=False) == set()


# -- what the caller gets --------------------------------------------------


async def test_the_row_carries_every_handle_needed_to_find_the_account():
    await make_user(1, days_ago=45, tier="free")
    row = (await users.get_inactive_users_for_cleanup(30, free_tier_enabled=True))[0]

    assert row["id"]
    assert row["telegram_id"] == 1
    assert row["remnawave_uuid"] == "11111111-1111-1111-1111-111111111111"
    assert row["remnawave_username"] == "u-1"


async def test_clearing_the_panel_identity_keeps_the_subscription_date():
    """
    The date is what stops a returning user getting a second trial, so it has
    to survive their panel account being deleted.
    """
    await make_user(1, days_ago=45, tier="free")
    row = await users.get_user_by_id(1)
    before = row["subscription_ends"]

    await users.clear_panel_identity(str(row["id"]))

    after = await users.get_user_by_id(1)
    assert after["remnawave_uuid"] is None
    assert after["remnawave_username"] is None
    assert after["squad_tier"] == "unknown"
    assert after["subscription_ends"] == before


async def test_a_cleared_user_is_not_selected_again():
    """Otherwise every pass would retry an account that is already gone."""
    await make_user(1, days_ago=45, tier="free")
    row = await users.get_user_by_id(1)
    await users.clear_panel_identity(str(row["id"]))

    assert await selected(free_tier=True) == set()


async def _pool():
    from tgvpn_shared.db.pool import get_pool

    return await get_pool()

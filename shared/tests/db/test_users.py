import time

import pytest

from tgvpn_shared.db import UserRepository
from tgvpn_shared.db.pool import get_pool
from tgvpn_shared.identity import plan_merge


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


async def test_create_and_fetch_round_trips_epoch_timestamps(users: UserRepository):
    now_ts = int(time.time())
    await users.create_user_record(111, "alice")

    row = await users.get_user_by_id(111)
    assert row is not None
    assert row["telegram_id"] == 111
    assert row["telegram_tag"] == "alice"
    assert row["subscription_ends"] == 0
    assert isinstance(row["created_at"], int)
    assert row["created_at"] >= now_ts


async def test_user_in_db(users: UserRepository):
    assert await users.user_in_db(222) is False
    await users.create_user_record(222, "bob")
    assert await users.user_in_db(222) is True


async def test_update_subscription_expire(users: UserRepository):
    await users.create_user_record(333, "carol")
    new_expire = int(time.time()) + 30 * 86400
    await users.update_subscription_expire(333, new_expire)

    row = await users.get_user_by_id(333)
    assert row["subscription_ends"] == new_expire


async def test_award_referral_is_atomic_and_one_shot(users: UserRepository):
    await users.create_user_record(1, "referrer")
    await users.create_user_record(2, "referred")
    await users.set_referrer_tag(2, "referrer")

    applied_first = await users.award_referral("referrer", 2)
    applied_second = await users.award_referral("referrer", 2)

    assert applied_first is True
    assert applied_second is False  # already referred -- must not double-count

    referrer_row = await users.get_user_by_id(1)
    assert referrer_row["referred_people"] == 1  # not 2


async def test_upsert_subscription_expire_does_not_wipe_other_columns(users: UserRepository):
    """Regression test for the admin_bot bug fixed in the earlier bug-fix pass:
    editing a user's expiry date must never reset referrals/gifts/tag."""
    await users.insert_subscription_user(
        telegram_id=42,
        subscription_ends=1000,
        telegram_tag="dave",
        referrer_tag="someone",
        gifted_subscriptions=3,
        referred_people=5,
    )

    new_expire = int(time.time()) + 60 * 86400
    await users.upsert_subscription_expire(42, new_expire)

    row = await users.get_user_by_id(42)
    assert row["subscription_ends"] == new_expire
    assert row["telegram_tag"] == "dave"
    assert row["referrer_tag"] == "someone"
    assert row["gifted_subscriptions"] == 3
    assert row["referred_people"] == 5


async def test_upsert_subscription_telegram_id_preserves_data_and_moves_id(users: UserRepository):
    await users.insert_subscription_user(
        telegram_id=100,
        subscription_ends=2000,
        referred_people=7,
    )

    await users.upsert_subscription_telegram_id(100, 200)

    assert await users.user_in_db(100) is False
    row = await users.get_user_by_id(200)
    assert row is not None
    assert row["referred_people"] == 7
    assert row["subscription_ends"] == 2000


async def test_get_inactive_telegram_ids_for_cleanup(users: UserRepository):
    long_ago = int(time.time()) - 90 * 86400
    recent = int(time.time()) + 10 * 86400
    await users.insert_subscription_user(telegram_id=500, subscription_ends=long_ago)
    await users.insert_subscription_user(telegram_id=501, subscription_ends=recent)

    inactive = await users.get_inactive_telegram_ids_for_cleanup(inactive_days=30)

    assert 500 in inactive
    assert 501 not in inactive


# -- merging a website account into a Telegram one --------------------------


async def _website_account(email: str, subscription_ends: int) -> str:
    """A row as the site creates one: an address, no Telegram identity."""
    pool = await get_pool()
    return str(
        await pool.fetchval(
            """
            INSERT INTO users (email, subscription_ends, created_at)
            VALUES ($1, to_timestamp($2), now())
            RETURNING id
            """,
            email, subscription_ends,
        )
    )


async def test_merging_moves_the_website_address_onto_the_survivor(users: UserRepository):
    """
    The regression that broke linking outright.

    `users.email` is UNIQUE, and the survivor used to adopt the website
    account's address while the website row still held it. Every link died on
    `users_email_key`, and all the bot could say was "попробуйте позже".
    """
    now = int(time.time())
    await users.create_user_record(901, "tg_user")
    telegram_row = await users.get_user_by_id(901)
    web_id = await _website_account("web@example.com", now + 10 * 86400)
    web_row = await users.get_user_by_uuid(web_id)

    plan = plan_merge(survivor=dict(telegram_row), absorbed=dict(web_row), now=now)
    await users.apply_merge(plan)

    survivor = await users.get_user_by_id(901)
    assert survivor["email"] == "web@example.com"
    # And the address is gone from the row that gave it up, or the write above
    # could not have landed at all.
    absorbed = await users.get_user_by_uuid(web_id)
    assert absorbed["id"] == survivor["id"], "the id should now resolve to the survivor"


async def test_an_address_the_survivor_keeps_leaves_the_other_one_alone(users: UserRepository):
    """
    Nothing is deleted when there is no collision to resolve: the absorbed
    address stays a working sign-in route, because the lookup follows
    `merged_into` to the survivor.
    """
    now = int(time.time())
    await users.create_user_record(902, "tg_user")
    await users.update_user_email(902, "mine@example.com")
    telegram_row = await users.get_user_by_id(902)
    web_id = await _website_account("other@example.com", now + 5 * 86400)
    web_row = await users.get_user_by_uuid(web_id)

    plan = plan_merge(survivor=dict(telegram_row), absorbed=dict(web_row), now=now)
    await users.apply_merge(plan)

    survivor = await users.get_user_by_id(902)
    assert survivor["email"] == "mine@example.com"
    reached = await users.get_user_by_email("other@example.com")
    assert reached is not None and reached["email"] == "other@example.com"


async def test_days_from_both_accounts_survive_the_merge(users: UserRepository):
    """The rule the whole feature rests on, asserted against real SQL."""
    now = int(time.time())
    await users.create_user_record(903, "tg_user")
    await users.update_subscription_expire(903, now + 14 * 86400)
    telegram_row = await users.get_user_by_id(903)
    web_id = await _website_account("sum@example.com", now + 30 * 86400)
    web_row = await users.get_user_by_uuid(web_id)

    plan = plan_merge(survivor=dict(telegram_row), absorbed=dict(web_row), now=now)
    await users.apply_merge(plan)

    survivor = await users.get_user_by_id(903)
    assert abs(survivor["subscription_ends"] - (now + 44 * 86400)) <= 1

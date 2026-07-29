import time

import pytest

from tgvpn_shared.db import UserRepository


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

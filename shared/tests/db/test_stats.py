"""Aggregate statistics queries, against a real database."""

import time

from tgvpn_shared.db import PaymentRepository, UserRepository

repo = UserRepository()
payments = PaymentRepository()

DAY = 86400


async def test_stats_on_an_empty_database():
    """Every count is zero, and nothing is None -- the report formats them directly."""
    stats = await repo.get_stats()
    assert stats["total"] == 0
    assert all(value == 0 for value in stats.values())


async def test_active_and_expired_split_on_the_current_time():
    now = int(time.time())
    await repo.insert_subscription_user(telegram_id=1, subscription_ends=now + 10 * DAY)
    await repo.insert_subscription_user(telegram_id=2, subscription_ends=now + 30 * DAY)
    await repo.insert_subscription_user(telegram_id=3, subscription_ends=now - DAY)

    stats = await repo.get_stats()
    assert stats["total"] == 3
    assert stats["active"] == 2
    assert stats["expired"] == 1


async def test_expiring_soon_uses_the_given_window():
    now = int(time.time())
    await repo.insert_subscription_user(telegram_id=1, subscription_ends=now + 2 * DAY)
    await repo.insert_subscription_user(telegram_id=2, subscription_ends=now + 10 * DAY)

    assert (await repo.get_stats(expiring_within_days=3))["expiring_soon"] == 1
    assert (await repo.get_stats(expiring_within_days=14))["expiring_soon"] == 2


async def test_already_expired_users_are_not_counted_as_expiring_soon():
    """Expiring-soon is a renewal-prompt number; an expired user already lapsed."""
    now = int(time.time())
    await repo.insert_subscription_user(telegram_id=1, subscription_ends=now - DAY)
    assert (await repo.get_stats())["expiring_soon"] == 0


async def test_referral_and_gift_totals_are_sums_not_counts():
    now = int(time.time())
    await repo.insert_subscription_user(
        telegram_id=1, subscription_ends=now, referred_people=3, gifted_subscriptions=2
    )
    await repo.insert_subscription_user(
        telegram_id=2, subscription_ends=now, referred_people=5, gifted_subscriptions=1
    )

    stats = await repo.get_stats()
    assert stats["referred_people"] == 8
    assert stats["gifted_subscriptions"] == 3


async def test_with_referrer_ignores_empty_strings():
    """`referrer_tag` defaults to '' rather than NULL on some insert paths."""
    now = int(time.time())
    await repo.insert_subscription_user(telegram_id=1, subscription_ends=now, referrer_tag="bob")
    await repo.insert_subscription_user(telegram_id=2, subscription_ends=now, referrer_tag="")
    await repo.insert_subscription_user(telegram_id=3, subscription_ends=now)

    assert (await repo.get_stats())["with_referrer"] == 1


async def test_new_user_windows_are_nested():
    now = int(time.time())
    await repo.insert_subscription_user(telegram_id=1, subscription_ends=now)

    stats = await repo.get_stats()
    assert stats["new_today"] == 1
    assert stats["new_week"] >= stats["new_today"]
    assert stats["new_month"] >= stats["new_week"]


async def test_payment_stats_split_by_status():
    await payments.update_payment_status("p1", "succeeded")
    await payments.update_payment_status("p2", "succeeded")
    await payments.update_payment_status("p3", "processing")
    await payments.update_payment_status("p4", "canceled")

    stats = await repo.get_payment_stats()
    assert stats["total"] == 4
    assert stats["succeeded"] == 2
    assert stats["processing"] == 1
    assert stats["failed"] == 1
    assert stats["succeeded_month"] == 2


async def test_payment_stats_on_an_empty_table():
    stats = await repo.get_payment_stats()
    assert stats["total"] == 0

import asyncio

import pytest

from tgvpn_shared.db import PromoRepository, UserRepository
from tgvpn_shared.db.pool import get_pool


@pytest.fixture
def promo() -> PromoRepository:
    return PromoRepository()


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


async def _seed_user(users: UserRepository, telegram_id: int) -> None:
    await users.create_user_record(telegram_id, f"user{telegram_id}")


async def test_one_time_claim_blocks_concurrent_double_redeem(promo: PromoRepository, users: UserRepository):
    """Gift-code race guarded by the earlier bug-fix pass: a one-time code
    must not be claimable by two users redeeming it at once."""
    await promo.create_gift_promo("GIFT-1", 30, creator_id=1)
    await _seed_user(users, 10)
    await _seed_user(users, 20)

    results = await asyncio.gather(
        promo.try_claim_promo_usage("GIFT-1", 10, one_time=True),
        promo.try_claim_promo_usage("GIFT-1", 20, one_time=True),
    )

    assert sorted(results) == [False, True]


async def test_multi_use_claim_is_per_user(promo: PromoRepository, users: UserRepository):
    await promo.insert_promo_code("DAYS-1", "days", 7, one_time=False)
    await _seed_user(users, 30)
    await _seed_user(users, 31)

    first_user_first_try = await promo.try_claim_promo_usage("DAYS-1", 30, one_time=False)
    first_user_second_try = await promo.try_claim_promo_usage("DAYS-1", 30, one_time=False)
    second_user_first_try = await promo.try_claim_promo_usage("DAYS-1", 31, one_time=False)

    assert first_user_first_try is True
    assert first_user_second_try is False
    assert second_user_first_try is True


async def test_release_promo_usage_allows_reclaim(promo: PromoRepository, users: UserRepository):
    await promo.insert_promo_code("DAYS-2", "days", 7, one_time=False)
    await _seed_user(users, 40)

    await promo.try_claim_promo_usage("DAYS-2", 40, one_time=False)
    await promo.release_promo_usage("DAYS-2", 40)

    reclaimed = await promo.try_claim_promo_usage("DAYS-2", 40, one_time=False)

    assert reclaimed is True


# -- who bought a gift ------------------------------------------------------


async def test_a_gift_records_the_buyer_by_internal_id(promo: PromoRepository, users: UserRepository):
    """
    The column the whole feature rests on. Without it a gift bought on the
    website recorded no creator at all: the code was charged for, delivered as
    a Telegram message to an account that does not exist, and reachable from
    no screen anywhere.
    """
    pool = await get_pool()
    buyer = str(
        await pool.fetchval(
            "INSERT INTO users (email, subscription_ends) VALUES ($1, to_timestamp(0)) RETURNING id",
            "buyer@example.com",
        )
    )

    await promo.create_gift_promo("GIFT-WEB", 30, creator_id=None, creator_user_id=buyer)

    row = await promo.get_promo_by_code("GIFT-WEB")
    assert str(row["creator_user_id"]) == buyer
    assert row["creator_id"] is None
    assert row["type"] == "gift"
    assert row["one_time"] is True


async def test_a_bot_purchase_still_records_the_telegram_id(promo: PromoRepository, users: UserRepository):
    """Support reads this column; nothing about the old path changes."""
    await _seed_user(users, 77)
    row = await users.get_user_by_id(77)

    await promo.create_gift_promo("GIFT-BOT", 30, creator_id=77, creator_user_id=str(row["id"]))

    stored = await promo.get_promo_by_code("GIFT-BOT")
    assert stored["creator_id"] == 77
    assert str(stored["creator_user_id"]) == str(row["id"])

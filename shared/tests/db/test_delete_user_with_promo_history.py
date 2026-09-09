"""
Deleting a user who has redeemed a code.

`promo_usage.user_id` used to reference `users(id)` with no `ON DELETE`
action, so the delete failed outright for anyone with a redemption on record
-- 82 real accounts on the production deployment, not an edge case. This is
the regression migration 0014 fixes: the row survives with `user_id` cleared
rather than blocking the delete, and the guarantees `try_claim_promo_usage`
depends on -- a one-time code cannot be reused, a user cannot double-claim a
reusable one -- have to survive that too.
"""

import pytest

from tgvpn_shared.db import PromoRepository, UserRepository


@pytest.fixture
def promo() -> PromoRepository:
    return PromoRepository()


@pytest.fixture
def users() -> UserRepository:
    return UserRepository()


async def _seed_user(users: UserRepository, telegram_id: int) -> str:
    await users.create_user_record(telegram_id, f"user{telegram_id}")
    row = await users.get_user_by_id(telegram_id)
    return str(row["id"])


async def test_a_user_who_redeemed_a_code_can_be_deleted(promo: PromoRepository, users: UserRepository):
    """The exact failure: `DELETE FROM users` used to raise a raw FK error."""
    await promo.create_gift_promo("GIFT-DEL", 30, creator_id=1)
    user_id = await _seed_user(users, 40)
    assert await promo.try_claim_promo_usage("GIFT-DEL", 40, one_time=True) is True

    assert await users.delete_user_row(user_id) is True


async def test_a_one_time_code_stays_spent_after_its_redeemer_is_deleted(
    promo: PromoRepository, users: UserRepository
):
    """
    The claim is guarded by the code's row existing at all, not by whose id is
    on it -- so nulling the id on delete must not reopen the code for a second
    person to redeem.
    """
    await promo.create_gift_promo("GIFT-GONE", 30, creator_id=1)
    user_id = await _seed_user(users, 41)
    await promo.try_claim_promo_usage("GIFT-GONE", 41, one_time=True)
    await users.delete_user_row(user_id)

    await _seed_user(users, 42)
    assert await promo.try_claim_promo_usage("GIFT-GONE", 42, one_time=True) is False


async def test_a_reusable_code_is_still_available_to_other_users_after_a_deletion(
    promo: PromoRepository, users: UserRepository
):
    """The ordinary case: one user leaving must not affect anyone else's claim."""
    await promo.insert_promo_code("STAYS", "days", 7, one_time=False)
    gone_id = await _seed_user(users, 43)
    await promo.try_claim_promo_usage("STAYS", 43, one_time=False)
    await users.delete_user_row(gone_id)

    await _seed_user(users, 44)
    assert await promo.try_claim_promo_usage("STAYS", 44, one_time=False) is True

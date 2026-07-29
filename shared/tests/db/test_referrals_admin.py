"""Admin-side referral writes, against a real database."""

from tgvpn_shared.db import UserRepository

repo = UserRepository()


async def _make_user(telegram_id: int, tag: str = "") -> None:
    await repo.insert_subscription_user(
        telegram_id=telegram_id, subscription_ends=0, telegram_tag=tag
    )


async def test_admin_can_overwrite_an_existing_referrer():
    """
    The customer-facing `set_referrer_tag` can only ever set a referrer once;
    the admin path exists precisely to correct a wrong one.
    """
    await _make_user(1001)
    await repo.set_referrer_tag(1001, "wrong_person")

    assert await repo.admin_set_referrer(1001, "right_person") is True

    row = await repo.get_user_by_id(1001)
    assert row["referrer_tag"] == "right_person"


async def test_admin_can_clear_a_referrer():
    await _make_user(1002)
    await repo.set_referrer_tag(1002, "someone")

    assert await repo.admin_set_referrer(1002, None) is True
    assert (await repo.get_user_by_id(1002))["referrer_tag"] is None


async def test_correcting_a_referrer_reopens_the_bonus():
    """
    A corrected referrer must still be able to earn their bonus, so the
    already-awarded flag is cleared along with the tag.
    """
    await _make_user(1003, tag="referrer_a")
    await _make_user(1004)
    await repo.set_referrer_tag(1004, "referrer_a")
    assert await repo.award_referral("referrer_a", 1004) is True
    assert (await repo.get_user_by_id(1004))["is_referred"] is True

    await repo.admin_set_referrer(1004, "referrer_b")
    assert (await repo.get_user_by_id(1004))["is_referred"] is False


async def test_the_previous_referrer_keeps_what_was_already_credited():
    """
    Reassigning does not decrement the old referrer: their counter is a total
    across everyone they invited, and clawing one back could remove credit for
    an unrelated referral.
    """
    await _make_user(1005, tag="referrer_a")
    await _make_user(1006)
    await repo.set_referrer_tag(1006, "referrer_a")
    await repo.award_referral("referrer_a", 1006)
    before = (await repo.get_user_by_id(1005))["referred_people"]

    await repo.admin_set_referrer(1006, "referrer_b")
    assert (await repo.get_user_by_id(1005))["referred_people"] == before


async def test_reset_awarded_can_be_disabled():
    await _make_user(1007)
    await repo.set_referrer_tag(1007, "referrer_a")
    await repo.award_referral("referrer_a", 1007)

    await repo.admin_set_referrer(1007, "referrer_b", reset_awarded=False)
    assert (await repo.get_user_by_id(1007))["is_referred"] is True


async def test_set_referred_people_overwrites_the_counter():
    await _make_user(1008)
    assert await repo.set_referred_people(1008, 42) is True
    assert (await repo.get_user_by_id(1008))["referred_people"] == 42


async def test_referred_people_never_goes_negative():
    await _make_user(1009)
    await repo.set_referred_people(1009, -5)
    assert (await repo.get_user_by_id(1009))["referred_people"] == 0


async def test_writes_to_a_missing_user_report_failure():
    assert await repo.admin_set_referrer(999_999_999, "x") is False
    assert await repo.set_referred_people(999_999_999, 1) is False

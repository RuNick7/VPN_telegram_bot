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
    assert await repo.set_referred_people(1008, 42) == 42
    assert (await repo.get_user_by_id(1008))["referred_people"] == 42


async def test_referred_people_never_goes_negative():
    await _make_user(1009)
    assert await repo.set_referred_people(1009, -5) == 0


async def test_count_can_be_set_without_the_user_having_a_referrer():
    """
    Granting a discount is independent of who (if anyone) invited this user --
    the counter is "people they brought in", not "who brought them".
    """
    await _make_user(1010)
    assert await repo.set_referred_people(1010, 5) == 5

    row = await repo.get_user_by_id(1010)
    assert row["referred_people"] == 5
    assert not row["referrer_tag"]


async def test_adjust_adds_and_subtracts_relative_to_the_current_value():
    await _make_user(1011)
    await repo.set_referred_people(1011, 4)

    assert await repo.adjust_referred_people(1011, 3) == 7
    assert await repo.adjust_referred_people(1011, -2) == 5


async def test_adjust_clamps_at_zero_rather_than_going_negative():
    await _make_user(1012)
    await repo.set_referred_people(1012, 2)
    assert await repo.adjust_referred_people(1012, -10) == 0


async def test_adjust_is_atomic_under_concurrent_edits():
    """
    Two admins bumping the counter at once must both land -- a read-then-write
    implementation would silently drop one of them.
    """
    import asyncio

    await _make_user(1013)
    await repo.set_referred_people(1013, 0)

    await asyncio.gather(*(repo.adjust_referred_people(1013, 1) for _ in range(10)))
    assert (await repo.get_user_by_id(1013))["referred_people"] == 10


async def test_writes_to_a_missing_user_report_failure():
    assert await repo.admin_set_referrer(999_999_999, "x") is False
    assert await repo.set_referred_people(999_999_999, 1) is None
    assert await repo.adjust_referred_people(999_999_999, 1) is None


# -- the same writes, addressed by our own id ------------------------------
#
# Which is the only handle an account created on the website has. Every method
# above is keyed on telegram_id and so could not touch one of those at all --
# the row was there, the columns were there, and the admin panel reported "нет
# telegram_id" and did nothing.

MISSING_ID = "00000000-0000-0000-0000-000000000000"


async def test_a_website_account_can_be_given_a_referrer():
    user_id = await repo.insert_web_user("referred@example.com", 0)

    assert await repo.admin_set_referrer_by_user_id(user_id, "inviter") is True
    assert (await repo.get_user_by_uuid(user_id))["referrer_tag"] == "inviter"


async def test_a_website_account_referrer_can_be_cleared():
    user_id = await repo.insert_web_user("clearme@example.com", 0)
    await repo.admin_set_referrer_by_user_id(user_id, "inviter")

    assert await repo.admin_set_referrer_by_user_id(user_id, None) is True
    assert (await repo.get_user_by_uuid(user_id))["referrer_tag"] is None


async def test_correcting_a_website_referrer_reopens_the_bonus():
    await _make_user(2001, tag="referrer_a")
    user_id = await repo.insert_web_user("reopen@example.com", 0)
    assert await repo.award_referral_by_user_id("referrer_a", user_id) is True
    assert (await repo.get_user_by_uuid(user_id))["is_referred"] is True

    await repo.admin_set_referrer_by_user_id(user_id, "referrer_b")
    assert (await repo.get_user_by_uuid(user_id))["is_referred"] is False


async def test_reset_awarded_can_be_disabled_by_user_id():
    await _make_user(2002, tag="referrer_a")
    user_id = await repo.insert_web_user("keepflag@example.com", 0)
    assert await repo.award_referral_by_user_id("referrer_a", user_id) is True

    await repo.admin_set_referrer_by_user_id(user_id, "referrer_b", reset_awarded=False)
    assert (await repo.get_user_by_uuid(user_id))["is_referred"] is True


async def test_a_website_account_count_can_be_set_and_adjusted():
    user_id = await repo.insert_web_user("counter@example.com", 0)

    assert await repo.set_referred_people_by_user_id(user_id, 4) == 4
    assert await repo.adjust_referred_people_by_user_id(user_id, 3) == 7
    assert await repo.adjust_referred_people_by_user_id(user_id, -2) == 5


async def test_a_website_account_count_clamps_at_zero():
    user_id = await repo.insert_web_user("clamp@example.com", 0)
    await repo.set_referred_people_by_user_id(user_id, 2)

    assert await repo.adjust_referred_people_by_user_id(user_id, -10) == 0
    assert await repo.set_referred_people_by_user_id(user_id, -5) == 0


async def test_by_user_id_writes_to_a_missing_row_report_failure():
    assert await repo.admin_set_referrer_by_user_id(MISSING_ID, "x") is False
    assert await repo.set_referred_people_by_user_id(MISSING_ID, 1) is None
    assert await repo.adjust_referred_people_by_user_id(MISSING_ID, 1) is None


# -- nobody invites themselves ---------------------------------------------


async def test_a_website_account_cannot_credit_its_own_telegram_tag():
    """
    The hole: an account created by email has no Telegram tag, so naming your
    own tag passes every check at the moment you type it. Linking that very
    Telegram is what makes the name resolve to you -- and the credit was the
    only gate left.
    """
    user_id = await repo.insert_web_user("selfref@example.com", 0)
    await repo.admin_set_referrer_by_user_id(user_id, "myself")
    await repo.attach_telegram(user_id, 3001, "myself")

    assert await repo.award_referral_by_user_id("myself", user_id) is False
    assert (await repo.get_user_by_uuid(user_id))["referred_people"] == 0


async def test_attaching_telegram_drops_a_referrer_that_is_now_yourself():
    user_id = await repo.insert_web_user("selfclear@example.com", 0)
    await repo.admin_set_referrer_by_user_id(user_id, "myself")

    await repo.attach_telegram(user_id, 3002, "myself")
    assert (await repo.get_user_by_uuid(user_id))["referrer_tag"] is None


async def test_attaching_telegram_leaves_a_real_referrer_alone():
    user_id = await repo.insert_web_user("keepref@example.com", 0)
    await repo.admin_set_referrer_by_user_id(user_id, "somebody_else")

    await repo.attach_telegram(user_id, 3003, "myself")
    assert (await repo.get_user_by_uuid(user_id))["referrer_tag"] == "somebody_else"


async def test_a_telegram_account_cannot_credit_its_own_tag():
    await _make_user(3004, tag="loner")
    await repo.set_referrer_tag(3004, "loner")

    assert await repo.award_referral("loner", 3004) is False
    assert (await repo.get_user_by_id(3004))["referred_people"] == 0


async def test_a_failed_self_referral_is_not_retryable():
    """`is_referred` is spent either way, or the attempt could be repeated
    until it happened to land on somebody real."""
    await _make_user(3005, tag="loner2")
    await repo.set_referrer_tag(3005, "loner2")
    await repo.award_referral("loner2", 3005)

    assert (await repo.get_user_by_id(3005))["is_referred"] is True


async def test_a_real_referrer_is_still_credited():
    await _make_user(3006, tag="inviter")
    await _make_user(3007, tag="invitee")

    assert await repo.award_referral("inviter", 3007) is True
    assert (await repo.get_user_by_id(3006))["referred_people"] == 1

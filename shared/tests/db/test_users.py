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


async def get_pool_execute(sql: str, *args):
    """Small escape hatch for setting up state no repository method writes."""
    pool = await get_pool()
    return await pool.execute(sql, *args)


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


# -- the two halves of the free period --------------------------------------


async def test_the_signup_trial_is_granted_once_and_only_once(users: UserRepository):
    await users.create_user_record(910, "newcomer")

    first = await users.grant_signup_trial_by_telegram_id(910, 7)
    second = await users.grant_signup_trial_by_telegram_id(910, 7)

    assert first is not None
    assert second is None, "a second call must not extend the subscription"
    row = await users.get_user_by_id(910)
    assert row["trial_signup_granted"] is True
    assert abs(row["subscription_ends"] - (int(time.time()) + 7 * 86400)) <= 2


async def test_a_returning_user_does_not_get_a_second_signup_trial(users: UserRepository):
    """
    The date is the older of the two guards and still load-bearing: the nightly
    cleanup deletes a lapsed user's panel account, and without this a trial
    would be renewable by waiting a month.
    """
    await users.insert_subscription_user(telegram_id=911, subscription_ends=int(time.time()) - 86400)

    assert await users.grant_signup_trial_by_telegram_id(911, 7) is None


async def test_the_link_bonus_lands_on_top_of_the_signup_trial(users: UserRepository):
    """The whole point: it is collected *after* the first grant moved the date."""
    now = int(time.time())
    await users.create_user_record(912, "linker")
    await users.grant_signup_trial_by_telegram_id(912, 7)
    row = await users.get_user_by_id(912)

    ends = await users.grant_link_bonus(str(row["id"]), 7)

    assert abs(ends - (now + 14 * 86400)) <= 2


async def test_the_link_bonus_is_granted_once_and_only_once(users: UserRepository):
    await users.create_user_record(913, "linker")
    row = await users.get_user_by_id(913)

    first = await users.grant_link_bonus(str(row["id"]), 7)
    second = await users.grant_link_bonus(str(row["id"]), 7)

    assert first is not None
    assert second is None


async def test_the_link_bonus_is_not_back_dated_for_a_lapsed_account(users: UserRepository):
    """
    GREATEST(subscription_ends, now()). Added to a date three weeks in the past
    it would produce a subscription that has already expired -- days paid for
    and never received.
    """
    now = int(time.time())
    await users.insert_subscription_user(telegram_id=914, subscription_ends=now - 21 * 86400)
    row = await users.get_user_by_id(914)

    ends = await users.grant_link_bonus(str(row["id"]), 7)

    assert abs(ends - (now + 7 * 86400)) <= 2


async def test_a_merge_leaves_no_room_for_a_third_free_period(users: UserRepository):
    """
    The cap, asserted end to end. Two accounts that each collected a signup
    trial merge to 14 days -- and the bonus is spent, so nothing can add a
    third 7 afterwards.
    """
    now = int(time.time())
    await users.create_user_record(915, "tg_user")
    await users.grant_signup_trial_by_telegram_id(915, 7)
    telegram_row = await users.get_user_by_id(915)

    web_id = await _website_account("cap@example.com", now + 7 * 86400)
    await get_pool_execute(
        "UPDATE users SET trial_signup_granted = TRUE WHERE id = $1::uuid", web_id
    )
    web_row = await users.get_user_by_uuid(web_id)

    plan = plan_merge(survivor=dict(telegram_row), absorbed=dict(web_row), now=now)
    await users.apply_merge(plan)

    survivor = await users.get_user_by_id(915)
    assert abs(survivor["subscription_ends"] - (now + 14 * 86400)) <= 2
    assert await users.grant_link_bonus(str(survivor["id"]), 7) is None


# -- binding a confirmed address --------------------------------------------


async def test_a_confirmed_address_lands_on_an_account_that_had_none(users: UserRepository):
    await users.create_user_record(920, "bot_user")
    row = await users.get_user_by_id(920)

    assert await users.bind_email(str(row["id"]), "Fresh@Example.COM") is True
    assert (await users.get_user_by_id(920))["email"] == "fresh@example.com"


async def test_an_address_somebody_else_holds_is_refused(users: UserRepository):
    """
    The address is a sign-in route. Moving one between accounts on the strength
    of a confirmation would let whoever controls a mailbox pull an account
    somebody else built onto it.
    """
    now = int(time.time())
    await _website_account("taken@example.com", now)
    await users.create_user_record(921, "bot_user")
    row = await users.get_user_by_id(921)

    assert await users.bind_email(str(row["id"]), "taken@example.com") is False
    assert (await users.get_user_by_id(921))["email"] is None


# -- the nurture campaign only chases people it can reach -------------------


async def test_nurture_skips_accounts_with_no_telegram(users: UserRepository):
    """
    A website account has no chat to message. It came back from this query
    anyway and was handed to SendMessage(chat_id=None), which failed
    validation once per user on every pass -- forever, and silently as far as
    anyone outside the log could tell.
    """
    await users.insert_web_user("nurture-web@example.com", 0)
    await users.insert_subscription_user(telegram_id=7001, subscription_ends=0)

    found = await users.get_users_for_nurture(now_ts=int(time.time()) + 60, target_stage=1, days_after=0)
    assert [row["telegram_id"] for row in found] == [7001]


async def test_nurture_skips_a_merged_away_row(users: UserRepository):
    """Its telegram_id is gone and its days now live on the survivor."""
    survivor_tg = 7002
    await users.insert_subscription_user(telegram_id=survivor_tg, subscription_ends=0)
    absorbed = await users.insert_web_user("nurture-merged@example.com", 0)

    survivor = await users.get_user_by_id(survivor_tg)
    plan = plan_merge(survivor=dict(survivor), absorbed=dict(await users.get_user_by_uuid(absorbed)),
                      now=int(time.time()))
    await users.apply_merge(plan)

    found = await users.get_users_for_nurture(now_ts=int(time.time()) + 60, target_stage=1, days_after=0)
    assert [row["telegram_id"] for row in found] == [survivor_tg]


# -- the admin picker lists our accounts, not the panel's profiles ---------


async def test_the_picker_lists_website_accounts(users: UserRepository):
    """
    The reason this query exists. Sourced from Remnawave, an account created on
    the website appears as `u-<uuid16>` -- and one whose panel profile failed
    to create does not appear at all.
    """
    await users.insert_web_user("picker-web@example.com", 0)
    await users.insert_subscription_user(telegram_id=8001, subscription_ends=0)

    rows = await users.list_accounts_page(50, 0)
    handles = {r["email"] or r["telegram_id"] for r in rows}
    assert handles == {"picker-web@example.com", 8001}
    assert await users.count_accounts() == 2


async def test_the_picker_hides_merged_away_rows(users: UserRepository):
    """Their days live on the survivor; picking one would edit a dead record."""
    await users.insert_subscription_user(telegram_id=8002, subscription_ends=0)
    absorbed = await users.insert_web_user("picker-merged@example.com", 0)
    survivor = await users.get_user_by_id(8002)

    await users.apply_merge(
        plan_merge(
            survivor=dict(survivor),
            absorbed=dict(await users.get_user_by_uuid(absorbed)),
            now=int(time.time()),
        )
    )

    rows = await users.list_accounts_page(50, 0)
    assert [r["telegram_id"] for r in rows] == [8002]
    assert await users.count_accounts() == 1


async def test_the_picker_pages_newest_first(users: UserRepository):
    for index in range(5):
        await users.insert_web_user(f"page{index}@example.com", 0)

    first = await users.list_accounts_page(2, 0)
    second = await users.list_accounts_page(2, 2)
    assert len(first) == 2 and len(second) == 2
    assert {r["email"] for r in first}.isdisjoint({r["email"] for r in second})
    assert await users.count_accounts() == 5

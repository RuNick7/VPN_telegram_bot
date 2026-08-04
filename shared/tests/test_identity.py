"""
Identity: what a person is called in the panel, and what merging two accounts
produces.

The merge arithmetic is what these mostly guard. Getting it wrong takes days
away from someone who paid for them, and does it silently -- nobody notices
until a customer counts.
"""

import pytest
from tgvpn_shared.identity import (
    PANEL_USERNAME_PREFIX,
    choose_survivor,
    days_from,
    legacy_panel_username,
    panel_username_for,
    plan_merge,
    resolve_panel_identity,
)

DAY = 86400
NOW = 1_800_000_000
GB = 1024**3

WEB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
TG_ID = "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301"


def account(**kwargs) -> dict:
    base = dict(
        id=TG_ID,
        telegram_id=555,
        subscription_ends=0,
        lte_paid_balance_bytes=0,
        gifted_subscriptions=0,
        referred_people=0,
        email=None,
        referrer_tag=None,
        remnawave_uuid=None,
        remnawave_username=None,
        trial_signup_granted=False,
        trial_link_granted=False,
    )
    return {**base, **kwargs}


# -- panel naming ----------------------------------------------------------


def test_a_new_account_is_named_from_our_own_id():
    """
    The whole point of the rework: an account can exist -- and be paid for --
    with no Telegram at all.
    """
    name = panel_username_for(WEB_ID)
    assert name.startswith(PANEL_USERNAME_PREFIX)
    assert "555" not in name


def test_the_panel_name_is_stable_for_a_user():
    assert panel_username_for(WEB_ID) == panel_username_for(WEB_ID)


def test_two_users_never_share_a_panel_name():
    assert panel_username_for(WEB_ID) != panel_username_for(TG_ID)


def test_the_go_side_derives_the_same_name():
    """
    web/internal/panel.UsernameFor must agree. The bot and the site create
    accounts for the same people; two names would mean two panel profiles.
    """
    assert panel_username_for("3f2504e0-4f89-11d3-9a0c-0305e82c3301") == "u-3f2504e04f8911d3"


def test_legacy_accounts_keep_their_telegram_name():
    """They are deliberately never renamed, so resolution must still find them."""
    assert legacy_panel_username(555) == "555"
    assert legacy_panel_username(None) is None


def test_lookup_prefers_the_stored_uuid():
    """
    It survives an operator renaming the account by hand, which neither of the
    name-based handles does.
    """
    lookup = resolve_panel_identity(
        account(remnawave_uuid="abc", remnawave_username="u-xyz", telegram_id=555)
    )
    assert lookup.uuid == "abc"
    assert lookup.username == "u-xyz"
    assert lookup.legacy_username == "555"


def test_a_web_only_user_is_still_findable():
    lookup = resolve_panel_identity(account(telegram_id=None, remnawave_username="u-xyz"))
    assert lookup.can_be_found
    assert lookup.legacy_username is None


def test_a_user_with_no_handles_at_all_cannot_be_found():
    """Better to say so than to look up `None` and get somebody else."""
    assert not resolve_panel_identity(account(telegram_id=None)).can_be_found


# -- merging ---------------------------------------------------------------


def test_the_telegram_side_survives():
    """
    Not because it matters more, but because `promo_usage.telegram_id` still
    references `users(telegram_id)` -- keeping that row avoids rewriting a
    foreign key under live data during a merge.
    """
    telegram, web = account(id=TG_ID), account(id=WEB_ID, telegram_id=None)
    survivor, absorbed = choose_survivor(telegram, web)
    assert survivor["id"] == TG_ID
    assert absorbed["id"] == WEB_ID


def test_days_add_up():
    """
    The headline behaviour. Someone who bought a month on the site and has two
    weeks left in the bot must end up with six weeks -- anything else takes
    time they paid for.
    """
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + 14 * DAY),
        absorbed=account(id=WEB_ID, subscription_ends=NOW + 30 * DAY),
        now=NOW,
    )
    assert days_from(plan.subscription_ends, NOW) == 44


def test_an_expired_account_contributes_nothing_rather_than_negative_days():
    """
    Two expiry timestamps cannot be added, and a lapsed one is in the past --
    summing raw dates would *shorten* the survivor's subscription.
    """
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + 10 * DAY),
        absorbed=account(id=WEB_ID, subscription_ends=NOW - 100 * DAY),
        now=NOW,
    )
    assert days_from(plan.subscription_ends, NOW) == 10


def test_merging_two_expired_accounts_does_not_invent_time():
    plan = plan_merge(
        survivor=account(subscription_ends=NOW - 5 * DAY),
        absorbed=account(id=WEB_ID, subscription_ends=NOW - 9 * DAY),
        now=NOW,
    )
    assert days_from(plan.subscription_ends, NOW) == 0


def test_purchased_traffic_adds_up():
    plan = plan_merge(
        survivor=account(lte_paid_balance_bytes=3 * GB),
        absorbed=account(id=WEB_ID, lte_paid_balance_bytes=5 * GB),
        now=NOW,
    )
    assert plan.lte_paid_balance_bytes == 8 * GB


def test_referrals_and_gifts_add_up():
    plan = plan_merge(
        survivor=account(referred_people=2, gifted_subscriptions=1),
        absorbed=account(id=WEB_ID, referred_people=3, gifted_subscriptions=4),
        now=NOW,
    )
    assert plan.referred_people == 5
    assert plan.gifted_subscriptions == 5


def test_the_survivors_email_is_never_overwritten():
    plan = plan_merge(
        survivor=account(email="mine@example.com"),
        absorbed=account(id=WEB_ID, email="other@example.com"),
        now=NOW,
    )
    assert plan.email == "mine@example.com"


def test_an_absent_email_is_filled_in_from_the_absorbed_account():
    plan = plan_merge(
        survivor=account(email=None),
        absorbed=account(id=WEB_ID, email="web@example.com"),
        now=NOW,
    )
    assert plan.email == "web@example.com"


def test_an_adopted_email_is_moved_rather_than_copied():
    """
    `users.email` is UNIQUE, so an address cannot sit on both rows at once.
    Copying it was the bug: every attempt to link a website account to a
    Telegram account died on `users_email_key`, and the bot could only say
    "попробуйте позже".
    """
    plan = plan_merge(
        survivor=account(email=None),
        absorbed=account(id=WEB_ID, email="web@example.com"),
        now=NOW,
    )
    assert plan.absorbed_releases_email is True


def test_an_address_the_survivor_does_not_take_stays_where_it_is():
    """
    Both addresses keep working -- the lookup follows `merged_into`, so the
    one left behind reaches the survivor anyway. Clearing it would silently
    delete a sign-in route the user still uses.
    """
    plan = plan_merge(
        survivor=account(email="mine@example.com"),
        absorbed=account(id=WEB_ID, email="other@example.com"),
        now=NOW,
    )
    assert plan.absorbed_releases_email is False


def test_a_merge_carries_the_signup_grant_from_either_side():
    """
    Their days have already been added together. Clearing the flag would let
    the merged account be handed a third free period by whichever side had not
    collected one.
    """
    for survivor_had, absorbed_had in [(True, False), (False, True), (True, True)]:
        plan = plan_merge(
            survivor=account(trial_signup_granted=survivor_had),
            absorbed=account(id=WEB_ID, trial_signup_granted=absorbed_had),
            now=NOW,
        )
        assert plan.trial_signup_granted is True


def test_a_merge_always_spends_the_link_bonus():
    """
    The bonus is paid for connecting a second identity, and a merge *is* that
    connection. Two accounts that each collected their own signup trial reach
    7 + 7 by addition; paying on top would make 21 free days reachable by
    registering twice on purpose.
    """
    plan = plan_merge(survivor=account(), absorbed=account(id=WEB_ID), now=NOW)
    assert plan.trial_link_granted is True


def test_nothing_is_released_when_the_absorbed_account_had_no_address():
    plan = plan_merge(
        survivor=account(email="mine@example.com"),
        absorbed=account(id=WEB_ID, email=None),
        now=NOW,
    )
    assert plan.absorbed_releases_email is False


def test_the_referrer_is_never_overwritten_either():
    """Changing who invited someone would move a discount they already earned."""
    plan = plan_merge(
        survivor=account(referrer_tag="alice"),
        absorbed=account(id=WEB_ID, referrer_tag="bob"),
        now=NOW,
    )
    assert plan.referrer_tag == "alice"


# -- panel accounts after a merge ------------------------------------------


def test_a_survivor_without_a_panel_account_adopts_the_other_one():
    """Otherwise the user loses the profile their link already points at."""
    plan = plan_merge(
        survivor=account(remnawave_uuid=None),
        absorbed=account(id=WEB_ID, remnawave_uuid="panel-web", remnawave_username="u-web"),
        now=NOW,
    )
    assert plan.adopt_panel_uuid == "panel-web"
    assert plan.adopt_panel_username == "u-web"
    assert plan.expire_panel_uuid is None


def test_a_leftover_panel_account_is_marked_for_expiry():
    """
    Its days were just added to the survivor. Leaving it live would hand the
    user the same period twice, on two working connection links.
    """
    plan = plan_merge(
        survivor=account(remnawave_uuid="panel-tg"),
        absorbed=account(id=WEB_ID, remnawave_uuid="panel-web"),
        now=NOW,
    )
    assert plan.expire_panel_uuid == "panel-web"
    assert plan.adopt_panel_uuid is None


def test_nothing_to_adopt_or_expire_when_only_the_survivor_has_a_profile():
    plan = plan_merge(
        survivor=account(remnawave_uuid="panel-tg"),
        absorbed=account(id=WEB_ID, remnawave_uuid=None),
        now=NOW,
    )
    assert plan.adopt_panel_uuid is None
    assert plan.expire_panel_uuid is None


def test_the_plan_names_both_sides():
    plan = plan_merge(survivor=account(), absorbed=account(id=WEB_ID), now=NOW)
    assert plan.survivor_id == TG_ID
    assert plan.absorbed_id == WEB_ID


@pytest.mark.parametrize(
    "timestamp, expected",
    [(NOW + 10 * DAY, 10), (NOW, 0), (NOW - DAY, 0), (NOW - 1, 0)],
)
def test_day_counting_never_goes_negative(timestamp, expected):
    assert days_from(timestamp, NOW) == expected


@pytest.mark.parametrize(
    "timestamp, expected",
    [
        # The one that mattered: seven days granted, read a moment later.
        (NOW + 7 * DAY - 1, 7),
        (NOW + DAY - 1, 1),
        (NOW + 1, 1),
        (NOW + 6 * DAY + 15 * 3600, 7),
    ],
)
def test_a_part_day_still_counts_as_a_day(timestamp, expected):
    """
    Rounded up.

    Truncation reported a freshly granted seven-day trial as "6 дн." -- the
    grant and the number contradicting each other on the same screen. Six days
    and fifteen hours of service left is seven days on which the subscription
    works.
    """
    assert days_from(timestamp, NOW) == expected


# -- the free period is one per person, not one per address ----------------


def test_two_signup_trials_do_not_add_up():
    """
    The abuse this closes, seen four times in production data: register with a
    new address, collect the free week, link the same Telegram, and the merge
    adds those days to the account that already had its own. Repeatable for as
    long as somebody has addresses.
    """
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + 7 * DAY, trial_signup_granted=True),
        absorbed=account(id=WEB_ID, subscription_ends=NOW + 7 * DAY,
                         trial_signup_granted=True),
        now=NOW,
        trial_days=7,
    )
    assert days_from(plan.subscription_ends, NOW) == 7


def test_paid_time_survives_the_deduction():
    """Only one trial's worth comes off; a month that was bought stays."""
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + 37 * DAY, trial_signup_granted=True),
        absorbed=account(id=WEB_ID, subscription_ends=NOW + 7 * DAY,
                         trial_signup_granted=True),
        now=NOW,
        trial_days=7,
    )
    assert days_from(plan.subscription_ends, NOW) == 37


def test_one_trial_between_them_still_adds_up():
    """
    Nothing is deducted when only one side ever had a free period -- the other
    side's days were bought, and taking them would be theft.
    """
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + 30 * DAY, trial_signup_granted=False),
        absorbed=account(id=WEB_ID, subscription_ends=NOW + 7 * DAY,
                         trial_signup_granted=True),
        now=NOW,
        trial_days=7,
    )
    assert days_from(plan.subscription_ends, NOW) == 37


def test_the_deduction_never_goes_negative():
    plan = plan_merge(
        survivor=account(subscription_ends=NOW + DAY, trial_signup_granted=True),
        absorbed=account(id=WEB_ID, subscription_ends=NOW + DAY,
                         trial_signup_granted=True),
        now=NOW,
        trial_days=30,
    )
    assert plan.subscription_ends == NOW

"""
Demotion/promotion planning.

`plan_membership` is deliberately pure: with hundreds of users on a
five-minute interval, deciding *whether* anything needs to change has to be
testable without a panel, and re-sending an identical membership every pass
would be most of the job's API traffic.
"""

import pytest
from tgvpn_shared.squads import SquadRoles

from app.scheduler.jobs.subscription_expire_monitor import (
    extract_squad_uuids,
    extract_telegram_id,
    resolve_subject,
    plan_membership,
)

ROLES = SquadRoles(free_uuid="free-1", lte_uuid="lte-1", paid_uuid="int-1")


def plan(current, *, active, paid="int-1"):
    result = plan_membership(
        ROLES, current, subscription_active=active, paid_squad_uuid=paid
    )
    return None if result is None else set(result)


# -- demotion --------------------------------------------------------------


def test_expired_paid_user_is_moved_to_free():
    assert plan(["int-1"], active=False) == {"free-1"}


def test_expired_user_keeps_lte_they_already_had():
    """
    LTE eligibility is about remaining balance, not paid-subscription status
    -- whether the quota is exhausted is the traffic monitor's call
    (`plan_quota`), not this job's.
    """
    assert plan(["int-1", "lte-1"], active=False) == {"free-1", "lte-1"}


def test_expired_user_already_on_free_needs_no_call():
    assert plan(["free-1"], active=False) is None


def test_expired_user_already_on_free_plus_lte_needs_no_call():
    assert plan(["free-1", "lte-1"], active=False) is None


# -- promotion -------------------------------------------------------------


def test_active_user_on_free_is_promoted():
    assert plan(["free-1"], active=True) == {"int-1"}


def test_active_user_already_paid_needs_no_call():
    assert plan(["int-1"], active=True) is None


def test_active_user_keeps_the_paid_squad_they_are_already_in():
    """Reassigning would shuffle users between pools for no reason."""
    assert plan(["int-2"], active=True, paid="int-2") is None


def test_promotion_clears_a_lingering_free_membership():
    assert plan(["int-1", "free-1"], active=True) == {"int-1"}


def test_promotion_preserves_existing_lte_access():
    """The LTE monitor owns that membership; this job must not fight it."""
    assert plan(["int-1", "lte-1", "free-1"], active=True) == {"int-1", "lte-1"}


def test_promotion_does_not_grant_lte_that_was_not_there():
    assert plan(["free-1"], active=True) == {"int-1"}


def test_no_available_paid_squad_defers_rather_than_demoting():
    """
    An active subscriber with nowhere to go must be left alone.

    Falling through to "FREE only" here would cut off paying users because of
    a capacity problem.
    """
    assert plan(["free-1"], active=True, paid=None) is None


# -- unmanaged squads ------------------------------------------------------


def test_squads_we_do_not_manage_survive_demotion():
    """An operator's hand-made squad is not ours to remove."""
    assert plan(["int-1", "vip"], active=False) == {"free-1", "vip"}


def test_squads_we_do_not_manage_survive_promotion():
    assert plan(["free-1", "vip"], active=True) == {"int-1", "vip"}


def test_user_in_only_an_unmanaged_squad_is_still_given_a_tier():
    assert plan(["vip"], active=True) == {"int-1", "vip"}
    assert plan(["vip"], active=False) == {"free-1", "vip"}


# -- panel field extraction ------------------------------------------------


@pytest.mark.parametrize(
    "user, expected",
    [
        ({"telegramId": 123}, 123),
        ({"telegram_id": 123}, 123),
        ({"telegramId": "123"}, 123),
        # Bot-created accounts are named after the Telegram ID, and older ones
        # predate telegramId being populated -- the username is the only link.
        ({"username": "7634241814"}, 7634241814),
        ({"username": "handmade"}, None),
        ({}, None),
        ({"telegramId": None, "username": "456"}, 456),
    ],
)
def test_extract_telegram_id(user, expected):
    assert extract_telegram_id(user) == expected


def test_extract_squad_uuids_skips_entries_without_one():
    user = {"activeInternalSquads": [{"uuid": "a"}, {"name": "no uuid"}, {"uuid": "b"}]}
    assert extract_squad_uuids(user) == ["a", "b"]


def test_extract_squad_uuids_on_a_user_with_none():
    assert extract_squad_uuids({}) == []
    assert extract_squad_uuids({"activeInternalSquads": None}) == []


# -- matching a panel account to one of our users --------------------------
#
# Two kinds of account exist now. One created by the bot carries a Telegram ID;
# one created on the website does not, and is matched by panel UUID instead.
# Before `resolve_subject` the second kind fell out of the loop entirely --
# never demoted when it lapsed, never tagged, and so never picked up by the
# free-squad cleanup either.


def test_a_telegram_account_is_matched_by_its_id():
    subject = resolve_subject({"uuid": "p1", "telegramId": 555}, {555: 900}, {})
    assert subject.telegram_id == 555
    assert subject.subscription_ends == 900


def test_a_website_account_is_matched_by_panel_uuid():
    """The regression this guards: no telegramId anywhere on the account."""
    rows = {"p1": {"id": "user-1", "telegram_id": None, "subscription_ends": 900}}
    subject = resolve_subject({"uuid": "p1", "username": "u-abc"}, {}, rows)

    assert subject is not None
    assert subject.user_id == "user-1"
    assert subject.subscription_ends == 900


def test_an_account_that_is_not_ours_is_skipped():
    """An operator made it by hand; moving it between squads is not ours to do."""
    assert resolve_subject({"uuid": "p9", "username": "manual"}, {}, {}) is None


def test_a_telegram_account_with_no_row_is_treated_as_expired():
    """
    The bot created it, so it is ours -- our row is just missing. Leaving it
    in a paid squad would be worse than demoting it.
    """
    subject = resolve_subject({"uuid": "p1", "telegramId": 555}, {}, {})
    assert subject is not None
    assert subject.subscription_ends == 0


def test_a_website_account_is_matched_on_a_numerically_named_panel():
    """
    The regression that made this whole job a no-op.

    A newer Remnawave identifies accounts by a numeric `id` and sends no
    `uuid` at all. Matching on that key alone found nothing, so nobody was
    demoted when their subscription lapsed and nobody promoted when they paid
    -- for months, with the job recording success on every pass.
    """
    rows = {"104": {"id": "user-1", "telegram_id": None, "subscription_ends": 900}}
    subject = resolve_subject({"id": 104, "username": "u-abc"}, {}, rows)

    assert subject is not None
    assert subject.user_id == "user-1"
    assert subject.subscription_ends == 900


def test_the_telegram_index_wins_over_the_uuid_index():
    """Cheaper, and it is the identity the bot will look them up by anyway."""
    rows = {"p1": {"id": "user-1", "telegram_id": 555, "subscription_ends": 1}}
    subject = resolve_subject({"uuid": "p1", "telegramId": 555}, {555: 900}, rows)
    assert subject.subscription_ends == 900
    assert subject.user_id is None

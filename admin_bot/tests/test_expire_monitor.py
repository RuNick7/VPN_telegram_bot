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
    plan_membership,
)

ROLES = SquadRoles(
    free_uuid="free-1", lte_uuid="lte-1", paid_uuids=frozenset({"int-1", "int-2"})
)


def plan(current, *, active, paid="int-1"):
    result = plan_membership(
        ROLES, current, subscription_active=active, paid_squad_uuid=paid
    )
    return None if result is None else set(result)


# -- demotion --------------------------------------------------------------


def test_expired_paid_user_is_moved_to_free():
    assert plan(["int-1"], active=False) == {"free-1"}


def test_expired_user_loses_lte_too():
    """Free mode means free servers, whatever traffic they had left."""
    assert plan(["int-1", "lte-1"], active=False) == {"free-1"}


def test_expired_user_already_on_free_needs_no_call():
    assert plan(["free-1"], active=False) is None


def test_expired_user_on_free_plus_lte_still_needs_fixing():
    assert plan(["free-1", "lte-1"], active=False) == {"free-1"}


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

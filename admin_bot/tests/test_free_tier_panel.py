"""
Panel-side FREE tier state: `expireAt` pushing and tier tagging.

The gap these cover: demoting to the FREE squad changes squad membership only.
A user whose `expireAt` had already passed when the feature was switched on
would land in the FREE squad with an expired account and still have nothing
working -- and they are precisely the population the feature exists for.
"""

import time

import pytest
from tgvpn_shared.free_tier import (
    TAG_FREE,
    TAG_PAID,
    format_panel_timestamp,
    needs_expire_push,
    needs_tag_update,
    parse_panel_timestamp,
    plan_panel_update,
    tier_tag,
)

DAY = 86400
NOW = 1_800_000_000


@pytest.fixture
def free_tier_on(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "free_tier_enabled", True)
    monkeypatch.setattr(settings, "free_tier_panel_expire_years", 10)


@pytest.fixture
def free_tier_off(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "free_tier_enabled", False)


# -- expireAt --------------------------------------------------------------


def test_a_past_expiry_needs_pushing():
    """The whole point: an already-expired account must not stay expired."""
    assert needs_expire_push(format_panel_timestamp(NOW - 7 * DAY), NOW) is True


def test_an_imminent_expiry_needs_pushing():
    assert needs_expire_push(format_panel_timestamp(NOW + 30 * DAY), NOW) is True


def test_an_already_far_future_expiry_is_left_alone():
    """Otherwise every pass would rewrite every user's date."""
    assert needs_expire_push(format_panel_timestamp(NOW + 3650 * DAY), NOW) is False


@pytest.mark.parametrize("value", [None, "", "not-a-date", "2026-13-45T99:99:99Z"])
def test_an_unreadable_expiry_is_treated_as_needing_a_push(value):
    """Leaving it alone risks the panel expiring an account we must keep alive."""
    assert needs_expire_push(value, NOW) is True


def test_timestamps_round_trip():
    assert parse_panel_timestamp(format_panel_timestamp(NOW)) == NOW


def test_panel_timestamp_format_is_what_the_api_expects():
    formatted = format_panel_timestamp(NOW)
    assert formatted.endswith("Z")
    assert "+00:00" not in formatted


# -- tags ------------------------------------------------------------------


def test_tier_tags_are_distinct():
    assert tier_tag("paid") == TAG_PAID
    assert tier_tag("free") == TAG_FREE
    assert TAG_PAID != TAG_FREE


def test_unknown_tier_is_rejected():
    with pytest.raises(ValueError):
        tier_tag("premium")


def test_an_untagged_user_gets_tagged():
    assert needs_tag_update(None, "free") is True
    assert needs_tag_update("", "free") is True


def test_a_correctly_tagged_user_is_left_alone():
    assert needs_tag_update(TAG_FREE, "free") is False


def test_our_own_tag_is_replaced_when_the_tier_changes():
    assert needs_tag_update(TAG_PAID, "free") is True


def test_an_operator_set_tag_is_never_overwritten():
    """
    Tagging someone "vip" in the panel by hand must survive reconciliation,
    not be clobbered every five minutes.
    """
    assert needs_tag_update("vip", "free") is False
    assert needs_tag_update("do-not-touch", "paid") is False


# -- combined plan ---------------------------------------------------------


def test_no_update_planned_when_the_feature_is_off(free_tier_off):
    """Deploying the code must change nothing until the flag is set."""
    user = {"expireAt": format_panel_timestamp(NOW - DAY), "tag": None}
    assert plan_panel_update(user=user, tier="free", now=NOW) is None


def test_an_expired_user_gets_both_a_future_date_and_a_tag(free_tier_on):
    user = {"expireAt": format_panel_timestamp(NOW - 7 * DAY), "tag": None}
    plan = plan_panel_update(user=user, tier="free", now=NOW)

    assert plan["tag"] == TAG_FREE
    assert parse_panel_timestamp(plan["expireAt"]) > NOW + 3000 * DAY


def test_an_already_correct_user_needs_no_call(free_tier_on):
    user = {"expireAt": format_panel_timestamp(NOW + 3650 * DAY), "tag": TAG_PAID}
    assert plan_panel_update(user=user, tier="paid", now=NOW) is None


def test_only_the_field_that_drifted_is_sent(free_tier_on):
    """Sending unchanged fields would be most of the job's API traffic."""
    user = {"expireAt": format_panel_timestamp(NOW + 3650 * DAY), "tag": TAG_PAID}
    plan = plan_panel_update(user=user, tier="free", now=NOW)
    assert plan == {"tag": TAG_FREE}


def test_snake_case_expiry_field_is_understood(free_tier_on):
    """Panel versions differ on expireAt vs expire_at."""
    user = {"expire_at": format_panel_timestamp(NOW + 3650 * DAY), "tag": TAG_FREE}
    assert plan_panel_update(user=user, tier="free", now=NOW) is None

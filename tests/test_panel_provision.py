"""
Deciding which users still need a panel account.

Two failure modes matter. Creating a *second* account for someone who already
has one splits their subscription across two links, neither of which is fully
right. And granting the trial to somebody who has already had one makes the
free period renewable by simply lapsing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from panel_provision import panel_username_for, plan_provisioning  # noqa: E402

DAY = 86400
NOW = 1_800_000_000
USER_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
OTHER_ID = "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301"
TRIAL = 30


def row(**kwargs) -> dict:
    base = dict(
        id=USER_ID,
        telegram_id=123456789,
        remnawave_uuid=None,
        remnawave_username=None,
        merged_into=None,
        subscription_ends=0,
    )
    return {**base, **kwargs}


def plan(rows, uuids=frozenset(), usernames=frozenset(), trial=TRIAL):
    return plan_provisioning(
        rows, set(uuids), set(usernames), now=NOW, trial_days=trial
    )


# -- creating --------------------------------------------------------------


def test_a_user_with_no_panel_account_gets_one():
    result = plan([row()])
    assert len(result.to_create) == 1
    assert result.to_create[0].username == panel_username_for(USER_ID)


def test_a_brand_new_user_gets_the_trial():
    """Nothing was ever granted to them, so this is their first free period."""
    item = plan([row(subscription_ends=0)]).to_create[0]
    assert item.trial_days == TRIAL
    assert item.expire_ts == NOW + TRIAL * DAY


def test_an_existing_subscription_is_restored_not_replaced():
    """
    Our database is the authority when the panel is being rebuilt from it --
    handing this user a trial instead would shorten what they paid for.
    """
    item = plan([row(subscription_ends=NOW + 100 * DAY)]).to_create[0]
    assert item.trial_days == 0
    assert item.expire_ts == NOW + 100 * DAY


def test_a_lapsed_user_is_restored_lapsed_rather_than_given_a_new_trial():
    """
    Otherwise a single run would hand a fresh trial to every dormant account
    at once, which is the whole population this script touches.
    """
    item = plan([row(subscription_ends=NOW - 60 * DAY)]).to_create[0]
    assert item.trial_days == 0
    assert item.expire_ts == NOW - 60 * DAY


def test_the_trial_can_be_switched_off():
    item = plan([row(subscription_ends=0)], trial=0).to_create[0]
    assert item.trial_days == 0


def test_a_website_account_without_telegram_is_still_provisioned():
    item = plan([row(telegram_id=None)]).to_create[0]
    assert item.telegram_id is None
    assert item.username.startswith("u-")


# -- not creating twice ----------------------------------------------------


def test_a_stored_uuid_present_in_the_panel_means_nothing_to_do():
    result = plan([row(remnawave_uuid="panel-1")], uuids={"panel-1"})
    assert result.to_create == []
    assert result.already_have == [USER_ID]


def test_an_account_found_by_its_stored_name_is_not_recreated():
    result = plan([row(remnawave_username="u-custom")], usernames={"u-custom"})
    assert result.to_create == []


def test_an_account_found_by_its_legacy_name_is_not_recreated():
    """
    The important one: a pre-rework user whose link was never recorded. Their
    panel account is named str(telegram_id), and creating a second one would
    split their subscription across two links.
    """
    result = plan([row(telegram_id=123456789)], usernames={"123456789"})
    assert result.to_create == []
    assert result.already_have == [USER_ID]


def test_an_account_found_by_the_name_we_would_mint_is_not_recreated():
    """Makes a re-run after a partly-failed run safe."""
    result = plan([row()], usernames={panel_username_for(USER_ID)})
    assert result.to_create == []


def test_a_stale_stored_uuid_does_not_block_creation():
    """
    The panel was rebuilt; the UUID we hold no longer exists there. The user
    genuinely has no account and needs one.
    """
    result = plan([row(remnawave_uuid="gone")], uuids={"something-else"})
    assert len(result.to_create) == 1


# -- skipping --------------------------------------------------------------


def test_merged_accounts_are_skipped():
    """They are not addressable any more; the survivor holds everything."""
    result = plan([row(merged_into=OTHER_ID)])
    assert result.to_create == []
    assert result.skipped == [(USER_ID, "account was merged into another")]


def test_a_row_without_an_id_is_skipped_rather_than_crashing():
    result = plan([row(id=None)])
    assert result.to_create == []
    assert len(result.skipped) == 1


# -- report ----------------------------------------------------------------


def test_counts_add_up():
    result = plan(
        [
            row(id=USER_ID, subscription_ends=0),
            row(id=OTHER_ID, telegram_id=999, remnawave_uuid="p2", subscription_ends=NOW + DAY),
            row(id="cccccccc-4f89-11d3-9a0c-0305e82c3301", merged_into=USER_ID),
        ],
        uuids={"p2"},
    )
    counts = result.counts()
    assert counts["users"] == 3
    assert counts["create"] == 1
    assert counts["with_trial"] == 1
    assert counts["already_have"] == 1
    assert counts["skipped"] == 1


def test_usernames_are_unique_per_user():
    assert panel_username_for(USER_ID) != panel_username_for(OTHER_ID)


def test_the_username_matches_the_shared_implementation():
    """Must equal identity.panel_username_for, or the bot and this disagree."""
    assert panel_username_for("3f2504e0-4f89-11d3-9a0c-0305e82c3301") == "u-3f2504e04f8911d3"

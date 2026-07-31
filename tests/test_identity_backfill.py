"""
Deciding what the identity backfill would write.

This script attaches panel accounts to people. Getting one wrong hands one
customer's subscription to another, and it is a one-off run against live data
that nobody watches closely -- so the tests below care mostly about the cases
where it must *refuse* rather than the ones where it works.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from identity_backfill import infer_telegram_id, is_own_username, plan_backfill  # noqa: E402

TG_ID = 123456789
USER_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
OTHER_ID = "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301"


def panel(**kwargs) -> dict:
    return {"uuid": "panel-1", "username": str(TG_ID), **kwargs}


def row(**kwargs) -> dict:
    return {"id": USER_ID, "telegram_id": TG_ID, "remnawave_uuid": None, **kwargs}


def only_plan(panel_users, db_rows):
    report = plan_backfill(panel_users, db_rows)
    assert len(report.plans) == 1
    return report.plans[0]


# -- working out whose account it is ---------------------------------------


def test_the_panels_own_field_wins_when_set():
    """An operator or an earlier create call put it there deliberately."""
    got, source = infer_telegram_id({"telegramId": TG_ID, "username": "999999999"})
    assert (got, source) == (TG_ID, "panel_field")


def test_a_numeric_username_is_the_fallback():
    """
    Every account created before the rework was named str(telegram_id) and
    carries no other link to a person -- without this they are unrecoverable.
    """
    assert infer_telegram_id({"username": str(TG_ID)}) == (TG_ID, "username")


def test_an_empty_panel_field_falls_through_rather_than_winning():
    for empty in (None, "", 0, "0"):
        assert infer_telegram_id({"telegramId": empty, "username": str(TG_ID)}) == (
            TG_ID, "username",
        )


def test_a_non_numeric_username_identifies_nobody():
    assert infer_telegram_id({"username": "alice"}) == (None, "unknown")
    assert infer_telegram_id({"username": "u-3f2504e04f89"}) == (None, "unknown")


@pytest.mark.parametrize("username", ["1", "42", "999", "9" * 25])
def test_digits_that_cannot_be_a_chat_id_are_rejected(username):
    """
    A panel account called "1" is a test account somebody made, not a person.
    Treating it as a Telegram ID would attach it to whoever owns that ID.
    """
    assert infer_telegram_id({"username": username}) == (None, "unknown")


def test_a_garbage_panel_field_does_not_crash_the_run():
    assert infer_telegram_id({"telegramId": "not-a-number", "username": "alice"}) == (
        None, "unknown",
    )


def test_new_style_usernames_are_recognisable():
    assert is_own_username({"username": "u-3f2504e04f8911d3"})
    assert not is_own_username({"username": str(TG_ID)})


# -- the happy path --------------------------------------------------------


def test_a_legacy_account_is_linked_to_its_user():
    plan = only_plan([panel()], [row()])
    assert plan.link_db
    assert plan.user_id == USER_ID
    assert plan.panel_uuid == "panel-1"
    assert plan.problem is None


def test_a_legacy_account_also_gets_its_panel_field_filled():
    """
    After this the account states its owner explicitly, so nothing has to
    parse a username ever again.
    """
    assert only_plan([panel()], [row()]).set_panel_telegram_id


def test_an_account_that_already_names_its_owner_needs_no_panel_write():
    plan = only_plan([panel(telegramId=TG_ID, username="u-abc")], [row()])
    assert plan.link_db
    assert not plan.set_panel_telegram_id


def test_an_already_linked_account_is_left_alone():
    """Re-running the script has to be free."""
    plan = only_plan([panel()], [row(remnawave_uuid="panel-1")])
    assert plan.is_noop
    assert not plan.link_db
    assert not plan.set_panel_telegram_id


# -- refusing to guess -----------------------------------------------------


def test_an_unidentifiable_account_is_reported_not_attached():
    plan = only_plan([panel(username="alice")], [row()])
    assert plan.problem is not None
    assert not plan.link_db


def test_two_panel_accounts_claiming_one_person_are_both_refused():
    """
    The dangerous case. Picking either one would be a coin flip deciding whose
    subscription somebody gets.
    """
    report = plan_backfill(
        [panel(uuid="panel-1"), panel(uuid="panel-2", telegramId=TG_ID, username="u-x")],
        [row()],
    )
    assert all(plan.problem for plan in report.plans)
    assert not any(plan.link_db for plan in report.plans)


def test_a_user_already_pointing_elsewhere_is_never_moved():
    """Overwriting the link would silently switch which account they use."""
    plan = only_plan([panel()], [row(remnawave_uuid="some-other-panel-account")])
    assert plan.problem is not None
    assert not plan.link_db


def test_a_panel_account_with_no_user_row_is_reported():
    plan = only_plan([panel()], [])
    assert plan.problem is not None
    assert not plan.link_db


def test_a_new_style_account_with_no_owner_is_reported_separately():
    """One we created and then lost the row for -- not a stranger's to claim."""
    plan = only_plan([panel(username="u-3f2504e04f8911d3")], [])
    assert "no matching user row" in plan.problem


def test_an_account_without_a_uuid_is_skipped():
    plan = only_plan([{"username": str(TG_ID)}], [row()])
    assert plan.problem is not None


# -- the report ------------------------------------------------------------


def test_users_with_no_panel_account_are_listed():
    """
    They cannot be linked, but knowing how many there are is the point of
    running this rather than relying on lazy backfill.
    """
    report = plan_backfill([], [row(), row(id=OTHER_ID, telegram_id=999999999)])
    assert len(report.users_without_panel) == 2


def test_counts_add_up():
    report = plan_backfill(
        [
            panel(uuid="p1", username=str(TG_ID)),
            panel(uuid="p2", username="alice"),
            panel(uuid="p3", username="987654321"),
        ],
        [row(), row(id=OTHER_ID, telegram_id=987654321, remnawave_uuid="p3")],
    )
    counts = report.counts()
    assert counts["total"] == 3
    assert counts["link_db"] == 1       # p1
    assert counts["problems"] == 1      # p2
    assert counts["already_done"] == 1  # p3


def test_nothing_is_planned_for_an_empty_panel():
    report = plan_backfill([], [])
    assert report.counts()["total"] == 0

"""The aggregate statistics report."""

import pytest

from app.handlers.admin.users.stats import build_report

DB = {
    "total": 495,
    "active": 300,
    "expired": 195,
    "expiring_soon": 12,
    "new_today": 3,
    "new_week": 21,
    "new_month": 88,
    "with_email": 140,
    "with_referrer": 57,
    "referrals_awarded": 40,
    "referred_people": 63,
    "gifted_subscriptions": 9,
}
PAYMENTS = {"total": 210, "succeeded": 190, "processing": 2, "failed": 18, "succeeded_month": 44}


def test_report_shows_every_headline_number():
    report = build_report(DB, PAYMENTS, panel_total=495, online_now=61)
    for value in ("495", "300", "195", "12", "88", "63", "190", "61"):
        assert value in report


def test_percentages_are_relative_to_total():
    report = build_report(DB, PAYMENTS, panel_total=495, online_now=None)
    assert "(61%)" in report  # 300/495 active
    assert "(39%)" in report  # 195/495 expired


def test_empty_database_does_not_divide_by_zero():
    empty = {key: 0 for key in DB}
    report = build_report(empty, {}, panel_total=0, online_now=0)
    assert "0%" in report


def test_missing_keys_fall_back_to_zero():
    """A stats query that gained a column shouldn't KeyError the whole screen."""
    report = build_report({"total": 5, "active": 5, "expired": 0}, {}, None, None)
    assert "5" in report


def test_panel_outage_is_reported_not_fatal():
    """The database half of the report is still useful when the panel is down."""
    report = build_report(DB, PAYMENTS, panel_total=None, online_now=None)
    assert "Панель недоступна" in report
    assert "495" in report


@pytest.mark.parametrize(
    "panel_total, expect_warning",
    [(495, False), (497, True), (490, True)],
)
def test_panel_database_drift_is_surfaced(panel_total, expect_warning):
    """
    A gap between panel and database counts means accounts exist on one side
    only -- exactly what an admin needs told, so it can't stay silent.
    """
    report = build_report(DB, PAYMENTS, panel_total=panel_total, online_now=10)
    assert ("Расхождение" in report) is expect_warning


def test_drift_is_signed_so_direction_is_readable():
    assert "+2" in build_report(DB, PAYMENTS, panel_total=497, online_now=None)
    assert "-5" in build_report(DB, PAYMENTS, panel_total=490, online_now=None)


def test_report_fits_in_one_telegram_message():
    """Telegram caps messages at 4096 characters; the old paged table existed
    to avoid that limit, so the replacement has to stay well under it."""
    assert len(build_report(DB, PAYMENTS, panel_total=495, online_now=61)) < 4096

"""
The list an operator picks a user out of.

It used to come from Remnawave, which holds *profiles*, not customers: an
account created on the website is named `u-<uuid16>` there and one whose
profile failed to create is absent entirely. Both were missing from the two
screens whose whole job is finding people.
"""

import time

import pytest

from app.handlers.admin.users.common import account_label

NOW = int(time.time())


def row(**kwargs) -> dict:
    base = dict(
        id="3f2504e0-4f89-11d3-9a0c-0305e82c3301",
        telegram_id=None,
        telegram_tag="",
        email=None,
        subscription_ends=0,
    )
    return {**base, **kwargs}


def test_a_telegram_user_reads_as_their_tag():
    assert account_label(row(telegram_id=555, telegram_tag="bob")).startswith("@bob")


def test_a_website_user_reads_as_their_address():
    """The case the panel-sourced list rendered as `u-3f2504e04f8911d3`."""
    assert account_label(row(email="buyer@example.com")).startswith("buyer@example.com")


def test_a_tagless_telegram_user_falls_back_to_the_id():
    assert account_label(row(telegram_id=555)).startswith("555")


def test_an_account_with_no_handle_at_all_is_still_labelled():
    label = account_label(row())
    assert label.startswith("3f2504e0")
    assert "None" not in label


def test_the_tag_wins_over_the_address():
    """An operator opens a chat far more often than they write an email."""
    assert account_label(
        row(telegram_id=555, telegram_tag="bob", email="bob@example.com")
    ).startswith("@bob")


@pytest.mark.parametrize(
    "ends, expected",
    [
        (0, "нет подписки"),
        (NOW - 86400, "истекла"),
        (NOW + 7 * 86400, "7 дн."),
        # Rounded up, matching the site: a part-day is a day it still works.
        (NOW + 6 * 86400 + 3600, "7 дн."),
    ],
)
def test_the_label_says_how_long_is_left(ends, expected):
    assert account_label(row(email="a@b.co", subscription_ends=ends)).endswith(expected)


def test_none_never_reaches_a_button():
    for candidate in (row(), row(telegram_id=555), row(email="a@b.co")):
        assert "None" not in account_label(candidate)

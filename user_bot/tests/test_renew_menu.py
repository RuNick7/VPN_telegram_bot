"""
Renewal entry points, and access when a subscription has lapsed.

Two behaviours here were previously wrong in ways that stranded users:
"Продлить" only ever offered plans, and an expired subscription replaced the
device menu entirely -- leaving a lapsed user with no route to their
connection link even though the link still worked.
"""

import pytest

from handlers.constants import PRICES
from handlers.keyboards import os_keyboard, renew_menu_keyboard
from handlers.utils import subscription_discount, subscription_label


def _callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


# -- renewal menu ----------------------------------------------------------


def test_the_device_menu_renew_button_opens_the_choice_not_plans():
    """
    Jumping straight to subscription plans made "I ran out of traffic" a dead
    end -- the user had to know about /traffic to get anywhere.
    """
    assert os_keyboard().inline_keyboard[-1][0].callback_data == "renew_menu"


def test_renew_menu_offers_both_purchases_when_lte_is_on():
    callbacks = _callbacks(renew_menu_keyboard(with_traffic=True))
    assert "subscription_tariffs" in callbacks
    assert "lte_packs" in callbacks


def test_renew_menu_hides_traffic_when_lte_is_off():
    """Selling traffic nothing meters would take money for nothing."""
    callbacks = _callbacks(renew_menu_keyboard(with_traffic=False))
    assert "subscription_tariffs" in callbacks
    assert "lte_packs" not in callbacks


def test_renew_menu_always_offers_a_way_back():
    assert "main_menu" in _callbacks(renew_menu_keyboard(with_traffic=False))


# -- subscription discounts ------------------------------------------------


@pytest.mark.parametrize(
    "months, expected",
    [(1, 0), (3, 6), (6, 10), (12, 15)],
)
def test_subscription_bulk_discount_at_tier_zero(months, expected):
    """
    Measured against paying monthly: 3 months at 89₽/mo would be 267₽, and it
    costs 249₽, so -6%.
    """
    price = PRICES[0][months]
    assert subscription_discount(months, price, 0) == expected


def test_one_month_shows_no_discount():
    """It is the baseline, so it cannot be a saving against itself."""
    assert subscription_discount(1, PRICES[0][1], 0) == 0
    assert subscription_label("1 месяц", 1, 89, 0) == "1 месяц — 89₽"


def test_the_discount_is_measured_at_the_users_own_tier():
    """
    Comparing a referral-discounted plan against the *full* monthly price
    would double-count: the referral saving would show up inside the bulk
    percentage as well as in the price itself.
    """
    tier = 3
    months = 12
    price = PRICES[tier][months]
    monthly = PRICES[tier][1]

    expected = int((1 - price / (months * monthly)) * 100)
    assert subscription_discount(months, price, tier) == expected


def test_discounts_are_whole_numbers():
    for tier in PRICES:
        for months, price in PRICES[tier].items():
            discount = subscription_discount(months, price, tier)
            assert isinstance(discount, int)
            assert 0 <= discount < 100


def test_labels_carry_the_percentage():
    assert subscription_label("3 месяца", 3, PRICES[0][3], 0) == "3 месяца — 249₽ (-6%)"


def test_a_plan_priced_worse_than_monthly_shows_no_saving():
    """Never advertise a markup as a discount."""
    assert subscription_discount(3, 999, 0) == 0
    assert "(-" not in subscription_label("3 месяца", 3, 999, 0)

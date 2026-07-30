"""
Buying LTE traffic.

Two properties matter most here: the price must come from our table rather
than from the user-controlled callback, and a traffic purchase must not touch
the subscription or award a referral bonus.
"""

import pytest

from handlers.constants import LTE_TRAFFIC_PACKS, PRICES
from handlers.keyboards import lte_packs_keyboard, os_keyboard, tariff_menu_keyboard


def test_the_advertised_packs_and_prices():
    assert LTE_TRAFFIC_PACKS == {5: 89, 10: 119, 15: 149, 30: 239}


def test_traffic_prices_are_flat_across_referral_tiers():
    """
    Traffic sits outside the referral discount ladder on purpose.

    Subscriptions get cheaper with referrals (PRICES is keyed by tier);
    traffic is a consumable resold at cost, so a five-referral user pays the
    same as everyone else. This guards against someone wiring it into the
    tiered table later.
    """
    assert not any(isinstance(price, dict) for price in LTE_TRAFFIC_PACKS.values())
    # The tiered table exists and does vary -- so flatness here is a choice,
    # not an accident of there being nothing to vary by.
    assert PRICES[0][1] != PRICES[5][1]


def test_larger_packs_cost_less_per_gigabyte():
    """A bigger pack must never be worse value, or nobody would buy one."""
    per_gb = [(gb, price / gb) for gb, price in sorted(LTE_TRAFFIC_PACKS.items())]
    rates = [rate for _gb, rate in per_gb]
    assert rates == sorted(rates, reverse=True), per_gb


def test_pack_keyboard_lists_every_pack_cheapest_first():
    rows = lte_packs_keyboard(LTE_TRAFFIC_PACKS).inline_keyboard
    pack_rows = rows[:-1]  # last row is "back"

    assert len(pack_rows) == len(LTE_TRAFFIC_PACKS)
    sizes = [int(row[0].callback_data.split(":")[1]) for row in pack_rows]
    assert sizes == sorted(LTE_TRAFFIC_PACKS)


def test_pack_buttons_show_size_and_price():
    labels = [row[0].text for row in lte_packs_keyboard(LTE_TRAFFIC_PACKS).inline_keyboard[:-1]]
    assert "5 ГБ — 89₽" in labels
    assert "30 ГБ — 239₽" in labels


def test_pack_callbacks_are_distinct():
    callbacks = [
        row[0].callback_data for row in lte_packs_keyboard(LTE_TRAFFIC_PACKS).inline_keyboard[:-1]
    ]
    assert len(set(callbacks)) == len(callbacks)


@pytest.mark.parametrize("spoofed", ["999", "0", "-5", "abc", ""])
def test_only_listed_packs_have_a_price(spoofed):
    """
    The handler looks the price up by size and refuses anything unlisted, so a
    hand-crafted `buy_lte:999` cannot name its own price.
    """
    try:
        size = int(spoofed)
    except ValueError:
        return
    assert LTE_TRAFFIC_PACKS.get(size) is None


def test_devices_menu_offers_renewal_at_the_bottom():
    rows = os_keyboard().inline_keyboard
    last_row = rows[-1]
    assert len(last_row) == 1
    assert last_row[0].callback_data == "subscription_tariffs"
    assert "Продлить" in last_row[0].text


def test_renewal_button_does_not_look_like_a_device():
    """`test_every_device_button_has_a_spec` matches on the `os:` prefix."""
    device_callbacks = [
        button.callback_data
        for row in os_keyboard().inline_keyboard
        for button in row
        if button.callback_data.startswith("os:")
    ]
    assert "subscription_tariffs" not in device_callbacks


def test_traffic_entry_is_hidden_when_lte_is_off():
    """Selling traffic that isn't metered would take money for nothing."""
    rows = tariff_menu_keyboard([("1 мес", "buy_tariff:1")], with_traffic=False).inline_keyboard
    assert all(button.callback_data != "lte_packs" for row in rows for button in row)


def test_traffic_entry_appears_when_lte_is_on():
    rows = tariff_menu_keyboard([("1 мес", "buy_tariff:1")], with_traffic=True).inline_keyboard
    assert any(button.callback_data == "lte_packs" for row in rows for button in row)

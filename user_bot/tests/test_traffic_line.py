"""
The whitelist-traffic balance shown in the devices menu.

Two things are being guarded. First, that the line tells the truth about
access: the quota monitor only grants the metered servers to paying users, so
a lapsed subscription must not be shown a balance it cannot spend. Second,
that reading the balance can never stop /start from opening -- the devices
menu is the only route to a user's connection link.
"""

from unittest.mock import AsyncMock

import pytest
from tgvpn_shared.lte_quota import TRAFFIC_LABEL
from tgvpn_shared.settings import get_settings

import handlers.menu as menu
from handlers.keyboards import renew_menu_keyboard, tariff_menu_keyboard

GB = 1024**3
NOW_CYCLE_START = 1  # long finished under any cycle length; usage reads fresh


def _state(**kwargs) -> dict:
    defaults = dict(
        lte_last_usage_bytes=0,
        lte_cycle_start=None,
        lte_paid_balance_bytes=0,
        lte_free_gb_override=None,
    )
    return {**defaults, **kwargs}


@pytest.fixture
def lte_on(monkeypatch):
    """Quotas enabled with a 10 GB monthly allowance."""
    settings = get_settings()
    # Instance-level: these are plain pydantic fields, not properties, so
    # patching the class does nothing.
    monkeypatch.setattr(settings, "lte_enabled", True)
    monkeypatch.setattr(settings, "lte_free_gb_per_cycle", 10)
    monkeypatch.setattr(settings, "lte_cycle_days", 30)
    return settings


def _repo(monkeypatch, state, *, raises: Exception | None = None):
    repo = AsyncMock()
    repo.get_state = AsyncMock(return_value=state, side_effect=raises)
    monkeypatch.setattr(menu, "_lte", repo)
    return repo


# -- what the line says ----------------------------------------------------


async def test_an_untouched_allowance_is_reported_in_full(monkeypatch, lte_on):
    _repo(monkeypatch, _state())
    line = await menu._traffic_line(1, subscription_active=True)
    assert TRAFFIC_LABEL in line
    assert "10.0 ГБ" in line


async def test_usage_and_purchases_are_both_reflected(monkeypatch, lte_on):
    _repo(monkeypatch, _state(lte_last_usage_bytes=8 * GB, lte_paid_balance_bytes=3 * GB))
    assert "5.0 ГБ" in await menu._traffic_line(1, subscription_active=True)


async def test_an_exhausted_balance_says_so_without_naming_a_command(monkeypatch, lte_on):
    """
    The menu this line sits in already carries a traffic button. Telling
    somebody to type `/traffic` a centimetre above the thing that does it was
    the wordier of two ways to say the same thing.
    """
    _repo(monkeypatch, _state(lte_last_usage_bytes=99 * GB))
    line = await menu._traffic_line(1, subscription_active=True)
    assert "закончился" in line
    assert "/traffic" not in line


async def test_the_line_ends_with_a_blank_line(monkeypatch, lte_on):
    """It is concatenated between the status block and 'Выберите устройство'."""
    _repo(monkeypatch, _state())
    assert (await menu._traffic_line(1, subscription_active=True)).endswith("\n\n")


# -- when it must not quote a balance --------------------------------------


async def test_a_lapsed_subscription_is_not_quoted_gigabytes(monkeypatch, lte_on):
    """
    The metered servers are paid-tier only -- `_apply_squad` refuses to hand
    them to anyone sitting on FREE. Showing "5 ГБ" to a lapsed user would
    advertise access they do not have.
    """
    _repo(monkeypatch, _state(lte_paid_balance_bytes=5 * GB))
    line = await menu._traffic_line(1, subscription_active=False)
    assert "ГБ" not in line
    assert "продлен" in line


async def test_nothing_is_shown_when_quotas_are_switched_off(monkeypatch, lte_on):
    """A figure nothing meters would be fiction."""
    monkeypatch.setattr(get_settings(), "lte_enabled", False)
    _repo(monkeypatch, _state(lte_paid_balance_bytes=5 * GB))
    assert await menu._traffic_line(1, subscription_active=True) == ""


async def test_quotas_off_does_not_even_read_the_database(monkeypatch, lte_on):
    monkeypatch.setattr(get_settings(), "lte_enabled", False)
    repo = _repo(monkeypatch, _state())
    await menu._traffic_line(1, subscription_active=True)
    repo.get_state.assert_not_awaited()


async def test_a_user_with_no_row_gets_no_line(monkeypatch, lte_on):
    _repo(monkeypatch, None)
    assert await menu._traffic_line(1, subscription_active=True) == ""


# -- failure must not close the menu ---------------------------------------


async def test_a_database_error_degrades_to_no_line(monkeypatch, lte_on):
    """
    /start has to open even when the balance cannot be read: this menu is the
    only route to a user's connection link.
    """
    _repo(monkeypatch, None, raises=RuntimeError("pool exhausted"))
    assert await menu._traffic_line(1, subscription_active=True) == ""


# -- naming ----------------------------------------------------------------


def test_the_customer_facing_name_is_not_an_abbreviation():
    """
    "LTE" is the internal name for the metered squad. It reads as the mobile
    standard and tells a customer nothing about what they are buying.
    """
    assert "LTE" not in TRAFFIC_LABEL
    assert "белых списков" in TRAFFIC_LABEL


@pytest.mark.parametrize(
    "keyboard",
    [
        renew_menu_keyboard(with_traffic=True),
        tariff_menu_keyboard([("1 мес", "buy_tariff:1")], with_traffic=True),
    ],
)
def test_every_traffic_button_uses_that_one_name(keyboard):
    """One wording everywhere, so the menus don't read as different products."""
    labels = [
        button.text
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data == "lte_packs"
    ]
    assert labels, "no traffic button found"
    assert all(TRAFFIC_LABEL in label for label in labels)


def test_callback_data_keeps_the_internal_name():
    """
    Renaming the wire format buys nothing a user can see and breaks every
    keyboard already sitting in a chat.
    """
    callbacks = [
        button.callback_data
        for row in renew_menu_keyboard(with_traffic=True).inline_keyboard
        for button in row
    ]
    assert "lte_packs" in callbacks

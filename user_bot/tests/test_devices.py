"""
Self-service device removal and connection-link reset.

The property worth most here is that a delete lands on the device the user
actually picked. Callback data caps at 64 bytes so the raw HWID cannot travel
in it, and the obvious alternative -- the device's position in the list --
would quietly point at a *different* device if the list changed between the
keyboard being drawn and the button being tapped. Several tests below exist
only to pin that down.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tgvpn_shared.remnawave import UserNotFoundError

import handlers.devices as devices
from handlers.devices import (
    device_label,
    device_token,
    devices_keyboard,
)
from handlers.keyboards import support_faq_back_to_devices_keyboard

IPHONE = {"hwid": "HW-IPHONE", "deviceModel": "iPhone 14", "platform": "ios", "osVersion": "17.2"}
LAPTOP = {"hwid": "HW-LAPTOP", "deviceModel": "MacBook Pro", "platform": "macos", "osVersion": "14"}


class FakeCallback:
    """Just enough CallbackQuery for these handlers."""

    def __init__(self, data: str = "", user_id: int = 555):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.alerts: list[str] = []
        self.sent: list[str] = []
        self.keyboards: list = []
        self.message = SimpleNamespace(answer=self._send, chat=SimpleNamespace(id=1))

    async def answer(self, text: str | None = None, **_kwargs):
        if text:
            self.alerts.append(text)

    async def _send(self, text: str, **kwargs):
        self.sent.append(text)
        self.keyboards.append(kwargs.get("reply_markup"))
        return SimpleNamespace()

    @property
    def last(self) -> str:
        return self.sent[-1]


@pytest.fixture
def panel(monkeypatch):
    """Panel calls stubbed out; no Remnawave is contacted."""
    stub = SimpleNamespace(
        get_devices=AsyncMock(return_value=([IPHONE, LAPTOP], 3)),
        delete_device=AsyncMock(return_value=None),
        reset_subscription_url=AsyncMock(return_value="https://sub/new-link"),
    )
    for name in ("get_devices", "delete_device", "reset_subscription_url"):
        monkeypatch.setattr(devices, name, getattr(stub, name))
    monkeypatch.setattr(devices, "get_client", lambda: SimpleNamespace(invalidate_token=lambda: None))
    return stub


def _callbacks(keyboard) -> list[str]:
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    ]


# -- addressing a device ---------------------------------------------------


def test_a_device_token_fits_in_callback_data():
    """
    Telegram rejects callback data over 64 bytes, and an HWID can be far
    longer than that on its own.
    """
    long_hwid = "X" * 400
    assert len(f"device_del_ok:{device_token(long_hwid)}".encode()) <= 64


def test_the_same_device_always_gets_the_same_token():
    assert device_token("HW-1") == device_token("HW-1")


def test_different_devices_get_different_tokens():
    assert device_token("HW-1") != device_token("HW-2")


def test_every_device_button_stays_within_the_callback_limit():
    keyboard = devices_keyboard([{**IPHONE, "hwid": "H" * 500}])
    assert all(len(data.encode()) <= 64 for data in _callbacks(keyboard))


def test_devices_without_an_identifier_get_no_button():
    """Nothing could be deleted by it, so a button would only mislead."""
    keyboard = devices_keyboard([{"deviceModel": "Ghost", "hwid": ""}])
    assert not [data for data in _callbacks(keyboard) if data.startswith("device_del:")]


# -- labels ----------------------------------------------------------------


def test_a_label_combines_model_platform_and_version():
    assert device_label(IPHONE) == "iPhone 14 · ios · 17.2"


def test_a_repeated_field_is_not_printed_twice():
    """Some panels report model and platform identically; "iPhone · iPhone" reads like a bug."""
    assert device_label({"deviceModel": "iPhone", "platform": "iPhone"}) == "iPhone"


def test_a_label_falls_back_to_the_user_agent():
    assert device_label({"userAgent": "Happ/1.2 iOS"}) == "Happ/1.2 iOS"


def test_an_unidentifiable_device_still_gets_a_name():
    assert device_label({}) == "Неизвестное устройство"


# -- listing ---------------------------------------------------------------


async def test_the_list_shows_each_device_and_the_limit(panel):
    cb = FakeCallback("my_devices")
    await devices.show_devices(cb)
    assert "iPhone 14" in cb.last
    assert "MacBook Pro" in cb.last
    assert "2 из 3" in cb.last


async def test_no_limit_means_a_bare_count(panel):
    panel.get_devices.return_value = ([IPHONE], None)
    cb = FakeCallback("my_devices")
    await devices.show_devices(cb)
    assert "(1)" in cb.last


async def test_an_empty_list_explains_where_devices_come_from(panel):
    panel.get_devices.return_value = ([], 3)
    cb = FakeCallback("my_devices")
    await devices.show_devices(cb)
    assert "после первого подключения" in cb.last
    assert not [d for d in _callbacks(cb.keyboards[-1]) if d.startswith("device_del")]


# -- deleting --------------------------------------------------------------


async def test_confirmation_does_not_delete_anything(panel):
    """The confirm screen is a question, not the action."""
    cb = FakeCallback(f"device_del:{device_token('HW-IPHONE')}")
    await devices.confirm_device_delete(cb)
    panel.delete_device.assert_not_awaited()
    assert "iPhone 14" in cb.last


async def test_confirming_deletes_the_device_that_was_picked(panel):
    cb = FakeCallback(f"device_del_ok:{device_token('HW-IPHONE')}")
    await devices.do_device_delete(cb)
    panel.delete_device.assert_awaited_once_with(555, "HW-IPHONE")


async def test_a_reordered_list_still_deletes_the_right_device(panel):
    """
    The reason devices are addressed by hash and not by position: the panel is
    free to return them in any order, and an index would land on whichever
    device happened to move into that slot.
    """
    panel.get_devices.return_value = ([LAPTOP, IPHONE], 3)
    cb = FakeCallback(f"device_del_ok:{device_token('HW-IPHONE')}")
    await devices.do_device_delete(cb)
    panel.delete_device.assert_awaited_once_with(555, "HW-IPHONE")


async def test_a_device_removed_elsewhere_deletes_nothing(panel):
    """
    A confirmation can sit in a chat for days. By the time it is tapped the
    device may be gone -- and deleting "whatever is there now" instead would
    be exactly the wrong recovery.
    """
    panel.get_devices.return_value = ([LAPTOP], 3)
    cb = FakeCallback(f"device_del_ok:{device_token('HW-IPHONE')}")
    await devices.do_device_delete(cb)
    panel.delete_device.assert_not_awaited()
    assert any("уже отключено" in alert for alert in cb.alerts)


async def test_a_forged_token_matches_nothing(panel):
    cb = FakeCallback("device_del_ok:deadbeefdeadbeef")
    await devices.do_device_delete(cb)
    panel.delete_device.assert_not_awaited()


async def test_a_failed_deletion_is_not_reported_as_success(panel):
    panel.delete_device.side_effect = RuntimeError("panel refused")
    cb = FakeCallback(f"device_del_ok:{device_token('HW-IPHONE')}")
    await devices.do_device_delete(cb)
    assert not any("Устройство отключено" in text for text in cb.sent)
    assert any("Не удалось" in alert for alert in cb.alerts)


# -- resetting the link ----------------------------------------------------


async def test_the_reset_prompt_touches_nothing(panel):
    """Asking must not be the same as doing -- every device would drop."""
    cb = FakeCallback("sub_reset")
    await devices.confirm_subscription_reset(cb)
    panel.reset_subscription_url.assert_not_awaited()


async def test_the_reset_prompt_states_the_consequence(panel):
    cb = FakeCallback("sub_reset")
    await devices.confirm_subscription_reset(cb)
    assert "перестанет работать" in cb.last
    assert "заново импортировать" in cb.last


async def test_confirming_rotates_the_link_and_shows_the_new_one(panel):
    cb = FakeCallback("sub_reset_ok")
    await devices.do_subscription_reset(cb)
    panel.reset_subscription_url.assert_awaited_once_with(555)
    assert "https://sub/new-link" in cb.last


async def test_a_rotation_that_returns_no_url_is_still_reported_as_done(panel):
    """
    The link is already dead at that point. Reporting failure would send the
    user round again on an old link that no longer works.
    """
    panel.reset_subscription_url.return_value = ""
    cb = FakeCallback("sub_reset_ok")
    await devices.do_subscription_reset(cb)
    assert "обновлена" in cb.last


async def test_a_failed_rotation_is_not_reported_as_done(panel):
    panel.reset_subscription_url.side_effect = RuntimeError("panel down")
    cb = FakeCallback("sub_reset_ok")
    await devices.do_subscription_reset(cb)
    assert not any("обновлена" in text for text in cb.sent)
    assert any("Не удалось" in alert for alert in cb.alerts)


# -- failure handling ------------------------------------------------------


async def test_a_slow_panel_says_so_instead_of_hanging(panel, monkeypatch):
    async def never_answers(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(devices, "PANEL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(devices, "get_devices", never_answers)
    cb = FakeCallback("my_devices")
    await devices.show_devices(cb)
    assert any("не отвечает" in alert for alert in cb.alerts)


async def test_a_missing_panel_profile_offers_to_subscribe(panel):
    panel.get_devices.side_effect = UserNotFoundError("gone")
    cb = FakeCallback("my_devices")
    await devices.show_devices(cb)
    assert "Профиль не найден" in cb.last


async def test_a_panel_error_drops_the_cached_token(panel, monkeypatch):
    """A stale cached token looks exactly like this failure."""
    invalidated = []
    monkeypatch.setattr(
        devices, "get_client", lambda: SimpleNamespace(invalidate_token=lambda: invalidated.append(1))
    )
    panel.get_devices.side_effect = RuntimeError("500")
    await devices.show_devices(FakeCallback("my_devices"))
    assert invalidated


# -- placement -------------------------------------------------------------


def test_both_actions_live_in_the_could_not_connect_menu():
    """
    Where the user already is when they cannot connect -- a device over the
    limit and a leaked link are two of the reasons they got there.
    """
    callbacks = _callbacks(support_faq_back_to_devices_keyboard())
    assert "my_devices" in callbacks
    assert "sub_reset" in callbacks


def test_that_menu_still_offers_its_original_help_routes():
    keyboard = support_faq_back_to_devices_keyboard()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any("поддержка" in label for label in labels)
    assert any("вопросы" in label for label in labels)
    assert any("Канал" in label for label in labels)

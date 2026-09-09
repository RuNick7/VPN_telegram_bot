"""
What the main menu offers once the FREE grace period has run out.

An expired subscription used to always open the device-setup menu, just with
different header text -- the free servers keep working, so there was always
somewhere for the buttons to point. Past `FREE_TIER_GRACE_DAYS`,
`inactive_user_cleanup` has removed the panel account entirely, and a device
button pointing at nothing is worse than no button: since `os:*` resolves the
account through the same lookup a payment does, tapping one would silently
recreate the very profile the cleanup job just deleted. Only "Продлить
подписку" is offered from that point on.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tgvpn_shared.free_tier import FREE_TIER_GRACE_DAYS

import handlers.menu as menu

DAY = 86400
NOW = 10_000_000


def row(*, subscription_ends: int) -> dict:
    return {
        "id": "row-uuid",
        "email": "x@example.com",  # short-circuits the email-bonus offer
        "trial_link_granted": True,
        "bonus_offer_shown_in_bot": True,
        "bonus_offer_dismissed": True,
        "subscription_ends": subscription_ends,
    }


class FakeMessage:
    """Just enough of a `types.Message` for `_render_main_menu`."""

    def __init__(self, user_id: int = 555):
        self.chat = SimpleNamespace(id=1)
        self.from_user = SimpleNamespace(id=user_id, username="tester")
        self.sent: list[dict] = []

        async def send_message(chat_id, text, **kwargs):
            self.sent.append({"chat_id": chat_id, "text": text, **kwargs})
            return SimpleNamespace()

        self.bot = SimpleNamespace(send_message=send_message)

    @property
    def last(self) -> dict:
        return self.sent[-1]


@pytest.fixture
def repo(monkeypatch):
    fake = SimpleNamespace(
        user_in_db=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(),
        update_telegram_tag=AsyncMock(),
    )
    monkeypatch.setattr(menu, "_users", fake)
    monkeypatch.setattr(menu, "get_settings", lambda: SimpleNamespace(lte_enabled=False))
    monkeypatch.setattr(menu.time, "time", lambda: NOW)
    return fake


def _callback_data(keyboard) -> list[str]:
    return [b.callback_data for r in keyboard.inline_keyboard for b in r if b.callback_data]


async def test_a_recently_expired_user_still_gets_the_device_menu(repo):
    """Inside the grace window, the existing downgrade-not-lockout behaviour holds."""
    repo.get_user_by_id.return_value = row(subscription_ends=NOW - (FREE_TIER_GRACE_DAYS - 1) * DAY)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "Подписка закончилась" in msg.last["text"]
    assert "os:ios" in _callback_data(msg.last["reply_markup"])


async def test_past_the_grace_window_only_renewal_is_offered(repo):
    repo.get_user_by_id.return_value = row(subscription_ends=NOW - (FREE_TIER_GRACE_DAYS + 1) * DAY)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    callbacks = _callback_data(msg.last["reply_markup"])
    assert callbacks == ["subscription_tariffs"]
    assert "os:" not in " ".join(callbacks)


async def test_past_the_grace_window_says_the_profile_is_gone(repo):
    repo.get_user_by_id.return_value = row(subscription_ends=NOW - (FREE_TIER_GRACE_DAYS + 1) * DAY)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "Продлите подписку" in msg.last["text"]
    assert "Выберите своё устройство" not in msg.last["text"]


async def test_exactly_thirty_days_matches_the_cleanup_jobs_own_cutoff(repo):
    """
    `< FREE_TIER_GRACE_DAYS`, not `<=`: the cleanup job deletes at
    `subscription_ends <= now() - 30 days` -- inclusive at exactly 30 days --
    so the menu must already show "past grace" at that same point, not one
    day later.
    """
    repo.get_user_by_id.return_value = row(subscription_ends=NOW - FREE_TIER_GRACE_DAYS * DAY)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert _callback_data(msg.last["reply_markup"]) == ["subscription_tariffs"]

"""
Low-traffic warnings.

The monitor runs every few minutes, so the interesting property is not "does
it warn" but "does it warn exactly once per threshold crossed" -- warning on
every pass would be a message every five minutes until the user topped up.
"""

from unittest.mock import AsyncMock, patch

import pytest
from tgvpn_shared.lte_quota import (
    LOW_TRAFFIC_THRESHOLDS_MB,
    low_traffic_threshold,
    remaining_bytes,
)

from app.scheduler.jobs.lte_traffic_monitor import (
    _maybe_warn_low_traffic,
    format_low_traffic_warning,
    traffic_topup_keyboard,
)
from app.scheduler.jobs.subscription_expire_monitor import Subject

MB = 1024**2
GB = 1024**3


# -- threshold selection ---------------------------------------------------


@pytest.mark.parametrize(
    "remaining_mb, expected",
    [
        (2000, 0),    # plenty left
        (501, 0),     # just above the first warning
        (500, 500),   # exactly at it
        (300, 500),   # between the two
        (151, 500),
        (150, 150),   # exactly at the second
        (10, 150),
        (0, 150),     # nothing left still reports the tightest level
    ],
)
def test_threshold_selection(remaining_mb, expected):
    assert low_traffic_threshold(remaining_mb * MB) == expected


def test_thresholds_are_ordered_loosest_first():
    """The message quotes the threshold, so their order is user-visible."""
    assert LOW_TRAFFIC_THRESHOLDS_MB == (500, 150)


def test_remaining_counts_allowance_and_purchased_traffic():
    assert remaining_bytes(usage_bytes=8 * GB, free_bytes=10 * GB, paid_balance=3 * GB) == 5 * GB


def test_remaining_never_goes_negative_on_overuse():
    """Usage past the allowance eats into purchased traffic, not below zero."""
    assert remaining_bytes(usage_bytes=15 * GB, free_bytes=10 * GB, paid_balance=0) == 0


# -- sending ---------------------------------------------------------------


def telegram_subject(telegram_id: int = 555) -> Subject:
    return Subject(telegram_id=telegram_id, user_id=None, subscription_ends=0)


def website_subject(user_id: str = "3f2504e0-4f89-11d3-9a0c-0305e82c3301") -> Subject:
    """Someone who signed up on the site: no Telegram account to message."""
    return Subject(telegram_id=None, user_id=user_id, subscription_ends=0)


async def _warn(remaining_mb: int, already_notified_mb: int, subject: Subject | None = None):
    repo = AsyncMock()
    notify = AsyncMock()
    with patch("app.scheduler.jobs.lte_traffic_monitor._lte", repo), patch(
        "app.scheduler.jobs.lte_traffic_monitor._notify_user", notify
    ):
        await _maybe_warn_low_traffic(
            subject or telegram_subject(),
            remaining=remaining_mb * MB,
            already_notified_mb=already_notified_mb,
        )
    return repo, notify


async def test_crossing_the_first_threshold_warns():
    repo, notify = await _warn(300, already_notified_mb=0)
    notify.assert_awaited_once()
    repo.set_low_traffic_notified.assert_awaited_once_with(555, 500)


async def test_staying_below_the_same_threshold_does_not_warn_again():
    """The property that stops a message every five minutes."""
    repo, notify = await _warn(200, already_notified_mb=500)
    notify.assert_not_awaited()
    repo.set_low_traffic_notified.assert_not_awaited()


async def test_crossing_the_second_threshold_warns_again():
    repo, notify = await _warn(100, already_notified_mb=500)
    notify.assert_awaited_once()
    repo.set_low_traffic_notified.assert_awaited_once_with(555, 150)


async def test_plenty_of_traffic_warns_nothing():
    _repo, notify = await _warn(5000, already_notified_mb=0)
    notify.assert_not_awaited()


async def test_a_topup_rearms_the_warning():
    """
    After topping up, the next slide downward must warn again rather than
    staying silent because the old flag was never cleared.
    """
    repo, notify = await _warn(5000, already_notified_mb=150)
    notify.assert_not_awaited()
    repo.set_low_traffic_notified.assert_awaited_once_with(555, 0)


async def test_a_blocked_user_does_not_stop_the_monitor():
    """
    Telegram rejects sends to users who blocked the bot; that must not abort
    the pass, and the flag still moves so we don't retry them every time.
    """
    repo = AsyncMock()
    notify = AsyncMock(side_effect=RuntimeError("bot was blocked by the user"))
    with patch("app.scheduler.jobs.lte_traffic_monitor._lte", repo), patch(
        "app.scheduler.jobs.lte_traffic_monitor._notify_user", notify
    ):
        await _maybe_warn_low_traffic(
            telegram_subject(), remaining=100 * MB, already_notified_mb=0
        )

    repo.set_low_traffic_notified.assert_awaited_once_with(555, 150)


# -- message ---------------------------------------------------------------


def test_the_warning_states_how_much_is_left():
    assert "300" in format_low_traffic_warning(500, 300 * MB)


def test_exhausted_traffic_says_so_rather_than_quoting_a_threshold():
    """"Under 150 MB left" reads wrong when the real answer is zero."""
    assert "закончился" in format_low_traffic_warning(150, 0)


def test_the_warning_reassures_that_other_servers_still_work():
    """Running out of metered traffic is not losing the VPN."""
    assert "серверы работают" in format_low_traffic_warning(150, 0)


@pytest.mark.parametrize("remaining", [0, 300 * MB])
def test_the_warning_names_no_command(remaining):
    """
    It used to end with "Докупить трафик: /traffic". Telling somebody to go
    and type something is the worst option available in a chat that has the
    message open -- the button below does it in one tap.
    """
    assert "/traffic" not in format_low_traffic_warning(150, remaining)


# -- the button ------------------------------------------------------------


def test_the_topup_button_is_the_callback_user_bot_handles():
    """
    The cross-process contract. This warning is composed in admin_bot and sent
    with *user_bot's* token, so the callback comes back to user_bot -- and a
    button naming something no handler is registered for would look to a
    customer like a broken bot rather than a typo.

    Pinned against the shared constant rather than the literal, because the
    two bots cannot be collected in one pytest process and this is the only
    place the agreement can be checked from.
    """
    from tgvpn_shared.lte_quota import TRAFFIC_TOPUP_CALLBACK

    button = traffic_topup_keyboard().inline_keyboard[0][0]
    assert button.callback_data == TRAFFIC_TOPUP_CALLBACK
    assert button.url is None


async def test_the_warning_goes_out_with_the_button_attached():
    """A message without it is the version this replaced."""
    repo = AsyncMock()
    notify = AsyncMock()
    with patch("app.scheduler.jobs.lte_traffic_monitor._lte", repo), patch(
        "app.scheduler.jobs.lte_traffic_monitor._notify_user", notify
    ):
        await _maybe_warn_low_traffic(
            telegram_subject(), remaining=100 * MB, already_notified_mb=0
        )

    assert notify.await_args.kwargs["reply_markup"].inline_keyboard


# -- users with no Telegram account ----------------------------------------


async def test_a_website_user_is_accounted_for_without_a_message(monkeypatch):
    """
    They have no chat to message, but the flag still has to move -- otherwise
    every pass would re-evaluate them as freshly crossed.
    """
    repo, notify = await _warn(100, already_notified_mb=0, subject=website_subject())

    notify.assert_not_awaited()
    repo.set_low_traffic_notified_by_user_id.assert_awaited_once_with(
        "3f2504e0-4f89-11d3-9a0c-0305e82c3301", 150
    )
    repo.set_low_traffic_notified.assert_not_awaited()


async def test_a_website_user_is_rearmed_on_recovery_too():
    repo, _notify = await _warn(5000, already_notified_mb=150, subject=website_subject())

    repo.set_low_traffic_notified_by_user_id.assert_awaited_once_with(
        "3f2504e0-4f89-11d3-9a0c-0305e82c3301", 0
    )

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
)

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


async def _warn(remaining_mb: int, already_notified_mb: int):
    repo = AsyncMock()
    notify = AsyncMock()
    with patch("app.scheduler.jobs.lte_traffic_monitor._lte", repo), patch(
        "app.scheduler.jobs.lte_traffic_monitor._notify_user", notify
    ):
        await _maybe_warn_low_traffic(
            555, remaining=remaining_mb * MB, already_notified_mb=already_notified_mb
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
        await _maybe_warn_low_traffic(555, remaining=100 * MB, already_notified_mb=0)

    repo.set_low_traffic_notified.assert_awaited_once_with(555, 150)


# -- message ---------------------------------------------------------------


def test_the_warning_states_how_much_is_left_and_where_to_top_up():
    message = format_low_traffic_warning(500, 300 * MB)
    assert "300" in message
    assert "/traffic" in message


def test_exhausted_traffic_says_so_rather_than_quoting_a_threshold():
    """"Under 150 MB left" reads wrong when the real answer is zero."""
    message = format_low_traffic_warning(150, 0)
    assert "закончился" in message
    assert "/traffic" in message


def test_the_warning_reassures_that_other_servers_still_work():
    """Running out of metered traffic is not losing the VPN."""
    assert "серверы работают" in format_low_traffic_warning(150, 0)

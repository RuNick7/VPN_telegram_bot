"""
The time-delayed messages: the expiry reminder and the nurture chain.

Both had defects that no amount of reading the copy would reveal -- one never
sent at all, the other sent everything at once.
"""

from unittest.mock import AsyncMock, patch

import pytest

from utils import reminders


@pytest.fixture
def bot() -> AsyncMock:
    return AsyncMock()


async def test_the_expiry_reminder_actually_reaches_the_user(bot):
    """
    It read `chat_id` from a row whose query selects no such column -- and the
    table has no such column either -- so every user was skipped with a warning
    and the reminder had never once been delivered.
    """
    repo = AsyncMock()
    repo.get_users_with_expiring_subscriptions = AsyncMock(
        return_value=[{"telegram_id": 555, "subscription_ends": 0, "telegram_tag": "bob"}]
    )
    repo.mark_reminded_if_needed = AsyncMock(return_value=True)

    with patch.object(reminders, "_users", repo):
        await reminders.send_reminders(bot)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 555


async def test_a_failed_send_releases_the_reminded_flag(bot):
    """Otherwise one Telegram hiccup costs that user their only warning."""
    repo = AsyncMock()
    repo.get_users_with_expiring_subscriptions = AsyncMock(
        return_value=[{"telegram_id": 555, "subscription_ends": 0, "telegram_tag": ""}]
    )
    repo.mark_reminded_if_needed = AsyncMock(return_value=True)
    bot.send_message = AsyncMock(side_effect=RuntimeError("blocked"))

    with patch.object(reminders, "_users", repo):
        await reminders.send_reminders(bot)

    repo.set_reminded_flag.assert_awaited_once_with(555, False)


async def test_an_already_reminded_user_is_not_told_twice(bot):
    repo = AsyncMock()
    repo.get_users_with_expiring_subscriptions = AsyncMock(
        return_value=[{"telegram_id": 555, "subscription_ends": 0, "telegram_tag": ""}]
    )
    repo.mark_reminded_if_needed = AsyncMock(return_value=False)

    with patch.object(reminders, "_users", repo):
        await reminders.send_reminders(bot)

    bot.send_message.assert_not_awaited()


async def test_one_nurture_stage_per_pass(bot):
    """
    The stages run newest-first. Ascending, each step handed the same person to
    the next: somebody sitting at stage 0 collected all four messages within a
    second of each other.
    """
    seen: list[int] = []

    async def fake_page(now_ts, target_stage, days_after):
        seen.append(target_stage)
        return []

    repo = AsyncMock()
    repo.get_users_for_nurture = AsyncMock(side_effect=fake_page)

    with patch.object(reminders, "_users", repo):
        for send in (
            reminders.send_nurture_3,
            reminders.send_nurture_2,
            reminders.send_nurture_1,
            reminders.send_nurture_channel,
        ):
            await send(bot, 0)

    assert seen == sorted(seen, reverse=True), "stages must be visited newest first"

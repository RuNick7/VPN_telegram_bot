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


async def _visit_stages(bot, monkeypatch) -> list[int]:
    """Run one scheduler pass and report which stages it asked for, in order."""
    # The site message asks for nothing when no site is configured, which is
    # the state a test environment is in. Give it one so the pass is complete.
    monkeypatch.setattr(reminders.get_settings(), "web_base_url", "https://example.test")
    seen: list[int] = []

    async def fake_page(now_ts, target_stage, days_after):
        seen.append(target_stage)
        return []

    repo = AsyncMock()
    repo.get_users_for_nurture = AsyncMock(side_effect=fake_page)

    with patch.object(reminders, "_users", repo):
        for send in reminders.NURTURE_SENDERS:
            await send(bot, 0)
    return seen


async def test_one_nurture_stage_per_pass(bot, monkeypatch):
    """
    Descending. Ascending, each step handed the person it had just advanced
    straight to the next, and anybody at stage 0 -- everyone who joined before
    the chain existed -- collected the whole series within a second.
    """
    seen = await _visit_stages(bot, monkeypatch)
    assert seen == sorted(seen, reverse=True), f"stages must descend, got {seen}"


async def test_every_stage_is_scheduled_exactly_once(bot, monkeypatch):
    """A gap in the numbering stalls the chain: nothing reaches the stage above."""
    seen = await _visit_stages(bot, monkeypatch)
    assert sorted(seen) == list(range(1, len(reminders.NURTURE_SENDERS) + 1))


async def test_the_trial_message_lands_before_the_trial_ends():
    """
    It used to fire on day 25 and open with "скоро закончится бесплатный
    период" -- eighteen days after a seven-day trial had ended.
    """
    from handlers.constants import trial_days

    repo = AsyncMock()
    repo.get_users_for_nurture = AsyncMock(return_value=[])

    with patch.object(reminders, "_users", repo):
        await reminders.send_nurture_3(AsyncMock(), 0)

    assert repo.get_users_for_nurture.await_args.kwargs["days_after"] < trial_days()


async def test_the_site_message_is_skipped_when_there_is_no_site(bot, monkeypatch):
    """Sending "у сервиса есть сайт" with no address in it helps nobody."""
    repo = AsyncMock()
    monkeypatch.setattr(reminders.get_settings(), "web_base_url", "")

    with patch.object(reminders, "_users", repo):
        await reminders.send_nurture_site(bot, 0)

    repo.get_users_for_nurture.assert_not_awaited()


async def test_the_channel_message_is_skipped_when_no_channel_is_set(bot, monkeypatch):
    """
    aiogram rejects a button with an empty `url`, so an unset address would
    fail the whole send rather than drop one link.
    """
    repo = AsyncMock()
    monkeypatch.setattr(reminders, "STATUS_CHANNEL_URL", "")

    with patch.object(reminders, "_users", repo):
        await reminders.send_nurture_channel(bot, 0)

    repo.get_users_for_nurture.assert_not_awaited()
    bot.send_message.assert_not_awaited()

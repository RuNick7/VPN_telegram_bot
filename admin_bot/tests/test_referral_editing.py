"""Admin-side referral editing (database-only fields)."""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Chat, Message, User

from app.handlers.admin.users.edit import (
    CLEAR_TOKENS,
    DB_ONLY_FIELDS,
    _apply_db_only_update,
    parse_count_input,
)

ADMIN = User(id=111, is_bot=False, first_name="Admin")


def make_message() -> tuple[Message, AsyncMock]:
    message = Message(
        message_id=1, date=0, chat=Chat(id=1, type="private"), from_user=ADMIN, text="@someone"
    )
    answer = AsyncMock()
    object.__setattr__(message, "answer", answer)
    return message, answer


def make_state(**data) -> AsyncMock:
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data)
    return state


def test_referral_fields_never_reach_the_panel():
    """
    Remnawave has no referral concept, so these must not be routed through
    `apply_update` -- doing so would send unknown fields to the panel.
    """
    assert DB_ONLY_FIELDS == {"referrer_tag", "referred_people"}


async def test_setting_a_referrer_strips_the_at_sign():
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referrer_tag", "@bob")

    repo.admin_set_referrer.assert_awaited_once_with(555, "bob")
    assert "✅" in answer.await_args.args[0]


@pytest.mark.parametrize("token", sorted(CLEAR_TOKENS))
async def test_clear_tokens_null_the_referrer(token):
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referrer_tag", token)

    repo.admin_set_referrer.assert_awaited_once_with(555, None)
    assert "очищен" in answer.await_args.args[0]


@pytest.mark.parametrize("bad", ["abc", "", "  ", "5x", "+", "-", "1.5"])
async def test_referred_people_rejects_non_numbers(bad):
    message, answer = make_message()
    repo = AsyncMock()

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", bad)

    repo.set_referred_people.assert_not_awaited()
    repo.adjust_referred_people.assert_not_awaited()
    assert "❌" in answer.await_args.args[0]


async def test_plain_number_sets_the_count():
    message, _ = make_message()
    repo = AsyncMock()
    repo.set_referred_people = AsyncMock(return_value=7)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "7")

    repo.set_referred_people.assert_awaited_once_with(555, 7)
    repo.adjust_referred_people.assert_not_awaited()


@pytest.mark.parametrize("text, delta", [("+3", 3), ("-2", -2), ("+ 3", 3)])
async def test_signed_number_adjusts_relatively(text, delta):
    """`+3` must add, not set to 3 -- the two differ for any non-zero start."""
    message, _ = make_message()
    repo = AsyncMock()
    repo.adjust_referred_people = AsyncMock(return_value=10)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", text)

    repo.adjust_referred_people.assert_awaited_once_with(555, delta)
    repo.set_referred_people.assert_not_awaited()


async def test_result_reports_the_resulting_discount_tier():
    """The count picks a price tier, so the admin is told what they granted."""
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people = AsyncMock(return_value=9)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "9")

    reply = answer.await_args.args[0]
    assert "9" in reply
    # Tier saturates at 5, so 9 referrals still reads as 5/5 rather than 9/5.
    assert "5/5" in reply


async def test_user_without_telegram_id_is_reported_not_silently_skipped():
    """
    Referral rows are keyed by telegram_id. A panel-only account has none, so
    there is nothing to update -- say so rather than reporting success.
    """
    message, answer = make_message()
    repo = AsyncMock()

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=None), "referrer_tag", "@bob")

    repo.admin_set_referrer.assert_not_awaited()
    assert "telegram_id" in answer.await_args.args[0]


async def test_missing_database_row_is_reported():
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer = AsyncMock(return_value=False)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referrer_tag", "@bob")

    assert "не найден" in answer.await_args.args[0]


async def test_missing_row_on_a_count_update_is_reported_not_treated_as_zero():
    """`None` means no such user; `0` is a legitimate new count."""
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people = AsyncMock(return_value=None)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "3")

    assert "не найден" in answer.await_args.args[0]


async def test_zero_is_a_valid_count_not_a_missing_user():
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people = AsyncMock(return_value=0)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "0")

    assert "✅" in answer.await_args.args[0]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("5", (5, False)),
        ("0", (0, False)),
        ("+3", (3, True)),
        ("-2", (-2, True)),
        ("+ 3", (3, True)),
        ("  7  ", (7, False)),
        ("abc", None),
        ("", None),
        ("+", None),
        ("1.5", None),
    ],
)
def test_parse_count_input(text, expected):
    assert parse_count_input(text) == expected

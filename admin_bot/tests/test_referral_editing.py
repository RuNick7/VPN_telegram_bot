"""Admin-side referral editing (database-only fields)."""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Chat, Message, User

from app.handlers.admin.users.edit import CLEAR_TOKENS, DB_ONLY_FIELDS, _apply_db_only_update

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


async def test_referred_people_requires_a_number():
    message, answer = make_message()
    repo = AsyncMock()

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "abc")

    repo.set_referred_people.assert_not_awaited()
    assert "числом" in answer.await_args.args[0]


async def test_referred_people_writes_the_count():
    message, _ = make_message()
    repo = AsyncMock()
    repo.set_referred_people = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(telegram_id=555), "referred_people", "7")

    repo.set_referred_people.assert_awaited_once_with(555, 7)


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

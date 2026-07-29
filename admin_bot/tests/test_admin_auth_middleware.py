"""
The admin authorization middleware.

These matter more than usual: this middleware is now the *only* thing standing
between a stranger and every admin handler, replacing ~70 per-handler checks.
"""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from app.middlewares.admin_auth import DENIED_TEXT, AdminAccessMiddleware

ADMIN = User(id=111, is_bot=False, first_name="Admin")
STRANGER = User(id=999, is_bot=False, first_name="Stranger")


def make_message() -> Message:
    message = Message(
        message_id=1,
        date=0,
        chat=Chat(id=1, type="private"),
        from_user=STRANGER,
        text="/admin",
    )
    object.__setattr__(message, "_answer", AsyncMock())
    return message


def make_callback() -> CallbackQuery:
    callback = CallbackQuery(
        id="1",
        from_user=STRANGER,
        chat_instance="ci",
        data="admin:menu",
    )
    object.__setattr__(callback, "_answer", AsyncMock())
    return callback


@pytest.fixture
def middleware():
    return AdminAccessMiddleware()


async def test_admin_reaches_the_handler(middleware):
    handler = AsyncMock(return_value="handled")
    event = make_message()

    with patch("app.middlewares.admin_auth.check_admin_access", AsyncMock(return_value=True)):
        result = await middleware(handler, event, {"event_from_user": ADMIN})

    assert result == "handled"
    handler.assert_awaited_once()


async def test_non_admin_message_is_blocked(middleware):
    handler = AsyncMock()
    event = make_message()
    answer = AsyncMock()
    object.__setattr__(event, "answer", answer)

    with patch("app.middlewares.admin_auth.check_admin_access", AsyncMock(return_value=False)):
        result = await middleware(handler, event, {"event_from_user": STRANGER})

    assert result is None
    handler.assert_not_awaited()
    answer.assert_awaited_once_with(DENIED_TEXT)


async def test_non_admin_callback_gets_an_alert(middleware):
    handler = AsyncMock()
    event = make_callback()
    answer = AsyncMock()
    object.__setattr__(event, "answer", answer)

    with patch("app.middlewares.admin_auth.check_admin_access", AsyncMock(return_value=False)):
        await middleware(handler, event, {"event_from_user": STRANGER})

    handler.assert_not_awaited()
    answer.assert_awaited_once_with(DENIED_TEXT, show_alert=True)


async def test_rejection_clears_any_in_progress_form(middleware):
    """
    A denied update must not leave FSM state behind.

    The old per-handler checks cleared state only where their author
    remembered to; doing it centrally means a stranger poking at a mid-form
    handler can't leave a half-filled form for the next authorized user.
    """
    handler = AsyncMock()
    event = make_message()
    object.__setattr__(event, "answer", AsyncMock())
    state = AsyncMock()

    with patch("app.middlewares.admin_auth.check_admin_access", AsyncMock(return_value=False)):
        await middleware(handler, event, {"event_from_user": STRANGER, "state": state})

    state.clear.assert_awaited_once()


async def test_update_without_a_sender_is_dropped(middleware):
    """No identifiable user means nothing to authorize -- and nothing to allow."""
    handler = AsyncMock()
    check = AsyncMock(return_value=True)

    with patch("app.middlewares.admin_auth.check_admin_access", check):
        result = await middleware(handler, make_message(), {})

    assert result is None
    handler.assert_not_awaited()
    check.assert_not_awaited()

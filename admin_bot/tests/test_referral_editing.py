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
WEB_ROW_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


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


def test_db_only_fields_never_reach_the_panel():
    """
    Remnawave has no concept of referrals, LTE quotas or our sign-in address,
    so these must not be routed through `apply_update` -- doing so would send
    unknown fields to the panel.
    """
    assert DB_ONLY_FIELDS == {
        "referrer_tag",
        "referred_people",
        "lte_free_gb",
        "lte_balance_gb",
        "email",
    }


async def test_setting_a_referrer_strips_the_at_sign():
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer_by_user_id = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referrer_tag", "@bob")

    repo.admin_set_referrer_by_user_id.assert_awaited_once_with(WEB_ROW_ID, "bob")
    assert "✅" in answer.await_args.args[0]


@pytest.mark.parametrize("token", sorted(CLEAR_TOKENS))
async def test_clear_tokens_null_the_referrer(token):
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer_by_user_id = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referrer_tag", token)

    repo.admin_set_referrer_by_user_id.assert_awaited_once_with(WEB_ROW_ID, None)
    assert "очищен" in answer.await_args.args[0]


@pytest.mark.parametrize("bad", ["abc", "", "  ", "5x", "+", "-", "1.5"])
async def test_referred_people_rejects_non_numbers(bad):
    message, answer = make_message()
    repo = AsyncMock()

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", bad)

    repo.set_referred_people_by_user_id.assert_not_awaited()
    repo.adjust_referred_people_by_user_id.assert_not_awaited()
    assert "❌" in answer.await_args.args[0]


async def test_plain_number_sets_the_count():
    message, _ = make_message()
    repo = AsyncMock()
    repo.set_referred_people_by_user_id = AsyncMock(return_value=7)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", "7")

    repo.set_referred_people_by_user_id.assert_awaited_once_with(WEB_ROW_ID, 7)
    repo.adjust_referred_people_by_user_id.assert_not_awaited()


@pytest.mark.parametrize("text, delta", [("+3", 3), ("-2", -2), ("+ 3", 3)])
async def test_signed_number_adjusts_relatively(text, delta):
    """`+3` must add, not set to 3 -- the two differ for any non-zero start."""
    message, _ = make_message()
    repo = AsyncMock()
    repo.adjust_referred_people_by_user_id = AsyncMock(return_value=10)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", text)

    repo.adjust_referred_people_by_user_id.assert_awaited_once_with(WEB_ROW_ID, delta)
    repo.set_referred_people_by_user_id.assert_not_awaited()


async def test_result_reports_the_resulting_discount_tier():
    """The count picks a price tier, so the admin is told what they granted."""
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people_by_user_id = AsyncMock(return_value=9)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", "9")

    reply = answer.await_args.args[0]
    assert "9" in reply
    # Tier saturates at 5, so 9 referrals still reads as 5/5 rather than 9/5.
    assert "5/5" in reply


@pytest.mark.parametrize(
    "field, value", [("referrer_tag", "@bob"), ("referred_people", "3")]
)
async def test_an_account_with_no_telegram_is_edited_not_refused(field, value):
    """
    The asymmetry this closes.

    These fields were addressed by telegram_id, so an account that signed up
    with an email -- which has none -- was told "нет telegram_id" and nothing
    was written, even though its row and its columns were right there. Identity
    is `users.id`; that is what they address now.
    """
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer_by_user_id = AsyncMock(return_value=True)
    repo.set_referred_people_by_user_id = AsyncMock(return_value=3)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(
            message, make_state(telegram_id=None, row_id=WEB_ROW_ID), field, value
        )

    assert "✅" in answer.await_args.args[0]


@pytest.mark.parametrize(
    "field, value",
    [
        ("referrer_tag", "@bob"),
        ("referred_people", "3"),
        ("lte_free_gb", "10"),
        ("lte_balance_gb", "+5"),
    ],
)
async def test_an_account_with_no_row_of_ours_is_reported(field, value):
    """
    A panel profile nothing else knows about. There is genuinely nothing to
    write -- say so rather than reporting success.
    """
    message, answer = make_message()
    repo = AsyncMock()
    lte = AsyncMock()

    with patch("app.handlers.admin.users.edit.users_repo", repo), patch(
        "app.handlers.admin.users.edit.lte_repo", lte
    ):
        await _apply_db_only_update(message, make_state(row_id=None), field, value)

    repo.admin_set_referrer_by_user_id.assert_not_awaited()
    repo.set_referred_people_by_user_id.assert_not_awaited()
    lte.set_free_gb_override_by_user_id.assert_not_awaited()
    lte.credit_balance_by_user_id.assert_not_awaited()
    assert "нет записи в нашей базе" in answer.await_args.args[0]


async def test_missing_database_row_is_reported():
    message, answer = make_message()
    repo = AsyncMock()
    repo.admin_set_referrer_by_user_id = AsyncMock(return_value=False)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referrer_tag", "@bob")

    assert "не найдена" in answer.await_args.args[0]


async def test_missing_row_on_a_count_update_is_reported_not_treated_as_zero():
    """`None` means no such user; `0` is a legitimate new count."""
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people_by_user_id = AsyncMock(return_value=None)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", "3")

    assert "не найдена" in answer.await_args.args[0]


async def test_zero_is_a_valid_count_not_a_missing_user():
    message, answer = make_message()
    repo = AsyncMock()
    repo.set_referred_people_by_user_id = AsyncMock(return_value=0)

    with patch("app.handlers.admin.users.edit.users_repo", repo):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "referred_people", "0")

    assert "✅" in answer.await_args.args[0]


# -- LTE quotas, the other half of the asymmetry ----------------------------


@pytest.mark.parametrize(
    "text, gigabytes", [("10", 10), ("0", 0), ("-", None)]
)
async def test_free_gb_override_is_written_by_our_id(text, gigabytes):
    """`0` is a real override meaning no free traffic; `-` clears it."""
    message, answer = make_message()
    lte = AsyncMock()
    lte.set_free_gb_override_by_user_id = AsyncMock(return_value=True)

    with patch("app.handlers.admin.users.edit.lte_repo", lte):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "lte_free_gb", text)

    lte.set_free_gb_override_by_user_id.assert_awaited_once_with(WEB_ROW_ID, gigabytes)
    assert "✅" in answer.await_args.args[0]


async def test_crediting_traffic_adds_rather_than_sets():
    """`+5` tops up; an absolute write here would erase a purchase."""
    message, _ = make_message()
    lte = AsyncMock()
    lte.credit_balance_by_user_id = AsyncMock(return_value=5 * 1024**3)

    with patch("app.handlers.admin.users.edit.lte_repo", lte):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "lte_balance_gb", "+5")

    lte.credit_balance_by_user_id.assert_awaited_once_with(WEB_ROW_ID, 5 * 1024**3)
    lte.set_balance_by_user_id.assert_not_awaited()


async def test_a_bare_number_sets_the_traffic_balance():
    message, _ = make_message()
    lte = AsyncMock()
    lte.set_balance_by_user_id = AsyncMock(return_value=0)

    with patch("app.handlers.admin.users.edit.lte_repo", lte):
        await _apply_db_only_update(message, make_state(row_id=WEB_ROW_ID), "lte_balance_gb", "0")

    lte.set_balance_by_user_id.assert_awaited_once_with(WEB_ROW_ID, 0)
    lte.credit_balance_by_user_id.assert_not_awaited()


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


# -- expiry has to reach both systems ---------------------------------------


async def test_extending_a_website_account_writes_our_row_too():
    """
    The bug this closes.

    `subscription_expire_monitor` decides who is expired from *our* column,
    not from the panel. A change that reached Remnawave alone was undone by
    the next monitor pass, which read the old date and demoted the user to the
    free squad -- and the write was keyed on telegram_id, which a website
    account does not have.
    """
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch

    from app.handlers.admin.users.edit import apply_update

    message, answer = make_message()
    state = make_state(user_uuid="panel-uuid", telegram_id=None, row_id=WEB_ROW_ID)
    repo = AsyncMock()
    expire_at = datetime(2026, 12, 31, tzinfo=timezone.utc)

    with patch("app.handlers.admin.users.edit.users_repo", repo), patch(
        "app.handlers.admin.users.edit.user_service", AsyncMock()
    ):
        await apply_update(message, state, {"expire_at": expire_at})

    repo.set_subscription_expire_by_user_id.assert_awaited_once_with(
        WEB_ROW_ID, int(expire_at.timestamp())
    )
    assert "и в базе" in answer.await_args.args[0]


async def test_extending_a_telegram_account_still_uses_the_telegram_path():
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch

    from app.handlers.admin.users.edit import apply_update

    message, _ = make_message()
    state = make_state(user_uuid="panel-uuid", telegram_id=555, row_id=WEB_ROW_ID)
    repo = AsyncMock()
    expire_at = datetime(2026, 12, 31, tzinfo=timezone.utc)

    with patch("app.handlers.admin.users.edit.users_repo", repo), patch(
        "app.handlers.admin.users.edit.user_service", AsyncMock()
    ):
        await apply_update(message, state, {"expire_at": expire_at})

    repo.upsert_subscription_expire.assert_awaited_once()
    repo.set_subscription_expire_by_user_id.assert_not_awaited()


async def test_a_panel_only_account_is_told_the_change_did_not_mirror():
    """
    Nothing of ours to write. Saying so is the point: silence here reads as
    success, and the site would keep showing the old date.
    """
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch

    from app.handlers.admin.users.edit import apply_update

    message, answer = make_message()
    state = make_state(user_uuid="panel-uuid", telegram_id=None, row_id=None)

    with patch("app.handlers.admin.users.edit.users_repo", AsyncMock()), patch(
        "app.handlers.admin.users.edit.user_service", AsyncMock()
    ):
        await apply_update(message, state, {"expire_at": datetime(2026, 12, 31, tzinfo=timezone.utc)})

    assert "только в Remnawave" in answer.await_args.args[0]

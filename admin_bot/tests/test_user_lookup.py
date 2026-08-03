"""
Finding a user by whatever handle the admin happens to have.

Every "type who you mean" prompt -- search, edit, delete -- goes through the
same resolver now. It used to be three different answers to the same question,
and the one they all agreed on, the panel username, is the one an admin is
least likely to have in front of them. A website account is not even named
after anything they would recognise.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.admin.users.common import find_db_row, find_panel_user, panel_names_for
from app.handlers.admin.users.search import build_summary

WEB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


def row(**kwargs) -> dict:
    base = dict(
        id=WEB_ID,
        telegram_id=None,
        telegram_tag="",
        email=None,
        subscription_ends=0,
        remnawave_username=None,
    )
    return {**base, **kwargs}


# -- which lookup a handle triggers ----------------------------------------


@pytest.mark.asyncio
async def test_digits_are_looked_up_as_a_telegram_id():
    repo = AsyncMock()
    repo.get_user_by_id.return_value = row(telegram_id=555)

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row("555")

    repo.get_user_by_id.assert_awaited_once_with(555)
    assert found["telegram_id"] == 555


@pytest.mark.asyncio
async def test_an_address_is_looked_up_as_an_email():
    # The handle a website account actually has. Before this it was not a
    # search term at all and the admin was told the user did not exist.
    repo = AsyncMock()
    repo.get_user_by_email.return_value = row(email="customer@example.com")

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row("customer@example.com")

    repo.get_user_by_email.assert_awaited_once_with("customer@example.com")
    assert found["email"] == "customer@example.com"


@pytest.mark.asyncio
async def test_an_at_prefixed_name_falls_back_to_the_tag():
    """`@nickname` contains an `@` but is not an address."""
    repo = AsyncMock()
    repo.get_user_by_email.return_value = None
    repo.get_user_by_tag.return_value = row(telegram_tag="nickname")

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row("@nickname")

    repo.get_user_by_tag.assert_awaited_once_with("nickname")
    assert found["telegram_tag"] == "nickname"


@pytest.mark.asyncio
async def test_anything_else_tries_uuid_then_panel_name_then_tag():
    repo = AsyncMock()
    repo.get_user_by_uuid.return_value = None
    repo.get_user_by_panel_username.return_value = row(remnawave_username="u-3f2504e04f8911d3")

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row("u-3f2504e04f8911d3")

    assert found["remnawave_username"] == "u-3f2504e04f8911d3"
    repo.get_user_by_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_nothing_found_is_none_rather_than_an_error():
    repo = AsyncMock()
    repo.get_user_by_uuid.return_value = None
    repo.get_user_by_panel_username.return_value = None
    repo.get_user_by_tag.return_value = None

    with patch("app.handlers.admin.users.common.users_repo", repo):
        assert await find_db_row("nobody") is None


# -- which name the panel is asked for -------------------------------------


def test_the_stored_panel_name_is_tried_first():
    # It is what we recorded when the account was created, and survives an
    # operator renaming things by hand.
    names = panel_names_for("555", row(telegram_id=555, remnawave_username="u-abc123"))
    assert names[0] == "u-abc123"


def test_a_legacy_account_is_still_found_by_its_telegram_id():
    """Accounts created before the identity rework are named after it."""
    names = panel_names_for("someone", row(telegram_id=555))
    assert "555" in names


def test_what_was_typed_is_always_tried():
    # Right when the admin copied a username straight out of Remnawave for an
    # account we have no row for at all.
    assert panel_names_for("u-typed", None) == ["u-typed"]


def test_the_same_name_is_not_tried_twice():
    names = panel_names_for("u-abc123", row(remnawave_username="u-abc123"))
    assert names == ["u-abc123"]


@pytest.mark.asyncio
async def test_a_panel_hit_reports_the_name_that_worked():
    service = AsyncMock()
    service.get_user_by_username.side_effect = [{}, {"uuid": "panel-uuid"}]

    with patch("app.handlers.admin.users.common.user_service", service):
        user, name = await find_panel_user("555", row(telegram_id=555, remnawave_username="u-abc"))

    assert user["uuid"] == "panel-uuid"
    assert name == "555"


@pytest.mark.asyncio
async def test_an_account_with_no_panel_profile_is_not_an_error():
    # Legitimate: the nightly cleanup deletes the panel account of a lapsed
    # user, and the row stays behind on purpose.
    service = AsyncMock()
    service.get_user_by_username.return_value = {}

    with patch("app.handlers.admin.users.common.user_service", service):
        assert await find_panel_user("555", None) == (None, None)


# -- the summary an admin actually reads -----------------------------------


def test_the_summary_leads_with_the_four_things_that_matter():
    import time

    text = "\n".join(
        build_summary(
            row(
                telegram_id=555,
                telegram_tag="nickname",
                email="customer@example.com",
                subscription_ends=int(time.time()) + 10 * 86400,
            )
        )
    )
    assert "555" in text
    assert "@nickname" in text
    assert "customer@example.com" in text
    assert "10" in text


def test_a_website_account_reads_as_having_no_telegram_rather_than_blank():
    text = "\n".join(build_summary(row(email="customer@example.com")))
    assert "—" in text
    assert "customer@example.com" in text


def test_a_lapsed_subscription_says_so_instead_of_showing_zero():
    import time

    text = "\n".join(build_summary(row(subscription_ends=int(time.time()) - 86400)))
    assert "истекла" in text

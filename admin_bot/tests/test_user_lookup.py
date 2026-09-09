"""
Finding a user by whatever handle the admin happens to have.

Every "type who you mean" prompt -- search, edit, delete -- goes through the
same resolver now. It used to be three different answers to the same question,
and the one they all agreed on, the panel username, is the one an admin is
least likely to have in front of them. A website account is not even named
after anything they would recognise.
"""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.handlers.admin.users.common import find_db_row, find_panel_user, panel_names_for
from app.handlers.admin.users.search import build_summary

WEB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
PANEL_NAME = "u-3f2504e04f8911d3"


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


def uuid_lookup(result=None):
    """
    A `get_user_by_uuid` that fails where the real one fails.

    `users.id` is a `uuid` column, so asyncpg types the parameter from it and
    rejects a malformed value before the query is sent -- looking a user up by
    something that is not an id *raises*. An `AsyncMock` returning None instead
    is more forgiving than the driver, and that gap is not academic: it is why
    the fallback below was asserted to work for two releases while an admin
    searching by panel username got `invalid UUID 'u-1ac936fdf3f94140'`.
    """

    async def lookup(value):
        UUID(str(value))
        return result

    return lookup


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
async def test_our_own_id_is_tried_before_the_other_handles():
    repo = AsyncMock()
    repo.get_user_by_uuid = uuid_lookup(row())

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row(WEB_ID)

    assert found["id"] == WEB_ID
    repo.get_user_by_panel_username.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_panel_username_is_not_offered_to_the_id_lookup():
    """
    The reported bug. `u-1ac936fdf3f94140` is minted from an id and reads like
    one, but it is not one, and asking anyway raises instead of returning
    nothing -- so the panel-name lookup that would have found the user never
    ran and the admin saw a driver error instead of a customer.
    """
    repo = AsyncMock()
    repo.get_user_by_uuid = uuid_lookup()
    repo.get_user_by_panel_username.return_value = row(remnawave_username=PANEL_NAME)

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row(PANEL_NAME)

    assert found["remnawave_username"] == PANEL_NAME
    repo.get_user_by_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_bare_nickname_reaches_the_tag_lookup():
    """
    Same crash, quieter: an admin who typed a nickname without its `@` was
    never told the user was missing either.
    """
    repo = AsyncMock()
    repo.get_user_by_uuid = uuid_lookup()
    repo.get_user_by_panel_username.return_value = None
    repo.get_user_by_tag.return_value = row(telegram_tag="nickname")

    with patch("app.handlers.admin.users.common.users_repo", repo):
        found = await find_db_row("nickname")

    assert found["telegram_tag"] == "nickname"


@pytest.mark.asyncio
async def test_nothing_found_is_none_rather_than_an_error():
    repo = AsyncMock()
    repo.get_user_by_uuid = uuid_lookup()
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


# -- traffic, the part search used to leave out ------------------------------


def test_an_account_the_metered_squad_never_touched_shows_no_traffic_line():
    """
    `lte_cycle_start` unset means no reading exists -- not "spent nothing".
    Fabricating a zero would say the wrong thing about 900+ legacy accounts
    that have never been near the metered squad.
    """
    text = "\n".join(build_summary(row()))
    assert "Трафик белых списков" not in text


def test_an_account_the_squad_has_touched_shows_spent_and_remaining():
    import time

    text = "\n".join(
        build_summary(
            row(
                lte_cycle_start=int(time.time()) - 3600,
                lte_last_usage_bytes=500 * 1024**2,
                lte_paid_balance_bytes=0,
            ),
            lte_free_gb_per_cycle=1,
            lte_cycle_seconds=30 * 86400,
        )
    )
    assert "потрачено" in text
    assert "500 МБ" in text
    assert "осталось" in text


def test_spent_is_the_raw_reading_not_a_total_minus_remaining():
    """
    An admin chasing "why was I blocked" needs the number the monitor actually
    measured -- not one reconstructed from the balance, which is exactly the
    derivation the site's own traffic tile stopped using for the same reason.
    """
    import time

    text = "\n".join(
        build_summary(
            row(
                lte_cycle_start=int(time.time()) - 3600,
                lte_last_usage_bytes=3 * 1024**3,
                lte_paid_balance_bytes=0,
            ),
            lte_free_gb_per_cycle=1,
            lte_cycle_seconds=30 * 86400,
        )
    )
    assert "3.0 ГБ" in text
    assert "осталось <b>0" in text


def test_a_blocked_account_says_so_in_the_traffic_line():
    import time

    text = "\n".join(
        build_summary(
            row(
                lte_cycle_start=int(time.time()) - 3600,
                lte_last_usage_bytes=2 * 1024**3,
                lte_paid_balance_bytes=0,
                lte_blocked=True,
            ),
            lte_free_gb_per_cycle=1,
            lte_cycle_seconds=30 * 86400,
        )
    )
    assert "заблокирован" in text

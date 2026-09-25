"""
Panel-account resolution for a Telegram user, including self-healing a
missing profile.

`_panel_user_for` backs every read/write that needs "this person's panel
account" -- devices, the subscription link, expiry. The tests below cover
only the recreate path added alongside the FREE tier: an account the FREE
tier promises should still work can nonetheless be missing from the panel --
an old pre-FREE-tier deletion, a manual removal -- and the fix is to put it
back the same way a payment already does (`create_panel_account`), rather
than telling someone who has already paid us once to go and subscribe.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tgvpn_shared.remnawave import UserNotFoundError

import app.services.remnawave.vpn_service as vpn_service

ROW = {"id": "row-uuid", "telegram_id": 555, "subscription_ends": 1_000_000}
PROFILE = {"uuid": "panel-uuid", "subscriptionUrl": "https://sub/link"}


@pytest.fixture
def repo(monkeypatch):
    fake = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=dict(ROW)),
        get_user_by_uuid=AsyncMock(return_value=dict(ROW)),
    )
    monkeypatch.setattr(vpn_service, "_users", fake)
    return fake


async def test_an_existing_profile_is_returned_without_touching_the_panel(repo, monkeypatch):
    monkeypatch.setattr(vpn_service, "resolve_panel_user", AsyncMock(return_value=PROFILE))
    create = AsyncMock()
    monkeypatch.setattr(vpn_service, "create_panel_account", create)

    user = await vpn_service._panel_user_for(555)

    assert user == PROFILE
    create.assert_not_awaited()


async def test_a_missing_profile_is_recreated(repo, monkeypatch):
    resolve = AsyncMock(side_effect=[None, PROFILE])
    create = AsyncMock(return_value=True)
    monkeypatch.setattr(vpn_service, "resolve_panel_user", resolve)
    monkeypatch.setattr(vpn_service, "create_panel_account", create)

    user = await vpn_service._panel_user_for(555)

    assert user == PROFILE
    create.assert_awaited_once_with(user_row=ROW, telegram_id=555, days_to_add=0)


async def test_recreation_does_not_add_days_to_the_subscription(repo, monkeypatch):
    """
    Restoring a lost profile is not a purchase -- `subscription_ends` in the
    database is untouched by this path; only the panel account comes back.
    """
    monkeypatch.setattr(vpn_service, "resolve_panel_user", AsyncMock(side_effect=[None, PROFILE]))
    create = AsyncMock(return_value=True)
    monkeypatch.setattr(vpn_service, "create_panel_account", create)

    await vpn_service._panel_user_for(555)

    assert create.await_args.kwargs["days_to_add"] == 0


async def test_a_failed_recreation_still_reports_the_profile_as_missing(repo, monkeypatch):
    monkeypatch.setattr(vpn_service, "resolve_panel_user", AsyncMock(return_value=None))
    monkeypatch.setattr(vpn_service, "create_panel_account", AsyncMock(return_value=False))

    with pytest.raises(UserNotFoundError):
        await vpn_service._panel_user_for(555)


async def test_a_reported_success_that_still_resolves_to_nothing_is_reported_as_missing(
    repo, monkeypatch
):
    """
    Guards a create that reports success but leaves nothing `resolve_panel_user`
    can find afterwards -- returning `None` up the call chain would break every
    caller, which all expect a dict back.
    """
    monkeypatch.setattr(vpn_service, "resolve_panel_user", AsyncMock(return_value=None))
    monkeypatch.setattr(vpn_service, "create_panel_account", AsyncMock(return_value=True))

    with pytest.raises(UserNotFoundError):
        await vpn_service._panel_user_for(555)


async def test_no_database_row_falls_back_to_the_legacy_lookup_without_recreating(monkeypatch):
    """Nothing to key a recreation off of -- `user_row["id"]` does not exist -- so this path is unchanged."""
    monkeypatch.setattr(
        vpn_service, "_users", SimpleNamespace(get_user_by_id=AsyncMock(return_value=None))
    )
    monkeypatch.setattr(
        vpn_service,
        "get_client",
        lambda: SimpleNamespace(find_user_by_username=AsyncMock(return_value=PROFILE)),
    )
    create = AsyncMock()
    monkeypatch.setattr(vpn_service, "create_panel_account", create)

    user = await vpn_service._panel_user_for(555)

    assert user == PROFILE
    create.assert_not_awaited()

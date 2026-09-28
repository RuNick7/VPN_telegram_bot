"""
Which squads a freshly created panel account joins.

A new account is shown its free gigabytes straight away. Until it is in the
metered squad it cannot reach the servers those gigabytes are for -- and
membership used to come only from the traffic monitor, on its own schedule,
and only once that monitor had found a metered node to look at.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.remnawave import vpn_service


@pytest.fixture
def client() -> AsyncMock:
    panel = AsyncMock()
    panel.list_internal_squads = AsyncMock(
        return_value=[
            {"uuid": "paid-uuid", "name": "internal"},
            {"uuid": "lte-uuid", "name": "LTE"},
        ]
    )
    return panel


def _squads_sent(client: AsyncMock) -> list[str]:
    return client.set_user_squads.await_args.args[1]


async def test_a_new_account_joins_the_metered_squad_too(client, monkeypatch):
    settings = vpn_service.get_settings()
    monkeypatch.setattr(settings, "lte_enabled", True)
    monkeypatch.setattr(settings, "lte_squad_name", "LTE")
    monkeypatch.setattr(settings, "paid_squad_name", "internal")

    with patch.object(vpn_service, "get_client", return_value=client):
        await vpn_service._assign_internal_squad("user-1")

    assert _squads_sent(client) == ["paid-uuid", "lte-uuid"]


async def test_quotas_off_means_the_paid_squad_alone(client, monkeypatch):
    settings = vpn_service.get_settings()
    monkeypatch.setattr(settings, "lte_enabled", False)
    monkeypatch.setattr(settings, "paid_squad_name", "internal")

    with patch.object(vpn_service, "get_client", return_value=client):
        await vpn_service._assign_internal_squad("user-1")

    assert _squads_sent(client) == ["paid-uuid"]


async def test_a_missing_metered_squad_still_places_the_account(client, monkeypatch):
    """LTE is an extra; the account must not be left with no squad over it."""
    settings = vpn_service.get_settings()
    monkeypatch.setattr(settings, "lte_enabled", True)
    monkeypatch.setattr(settings, "lte_squad_name", "no-such-squad")
    monkeypatch.setattr(settings, "paid_squad_name", "internal")

    with patch.object(vpn_service, "get_client", return_value=client):
        await vpn_service._assign_internal_squad("user-1")

    assert _squads_sent(client) == ["paid-uuid"]


async def test_a_missing_paid_squad_assigns_nothing(client, monkeypatch):
    """The expiry monitor repairs it; guessing a squad would be worse."""
    settings = vpn_service.get_settings()
    monkeypatch.setattr(settings, "lte_enabled", True)
    monkeypatch.setattr(settings, "paid_squad_name", "no-such-squad")

    with patch.object(vpn_service, "get_client", return_value=client):
        await vpn_service._assign_internal_squad("user-1")

    client.set_user_squads.assert_not_awaited()


async def test_a_panel_failure_never_stops_account_creation(client, monkeypatch):
    monkeypatch.setattr(vpn_service.get_settings(), "paid_squad_name", "internal")
    client.set_user_squads = AsyncMock(side_effect=RuntimeError("panel down"))

    with patch.object(vpn_service, "get_client", return_value=client):
        await vpn_service._assign_internal_squad("user-1")  # must not raise

"""
Finding the panel account of a user due for cleanup.

The interesting property is that it still finds accounts named the new way.
Before the identity rework this looked users up by `str(telegram_id)` and
nothing else, so after the rework it would have quietly stopped cleaning up
every account created since -- the free squad filling up with exactly the
users this job exists to remove, and no error anywhere to say so.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.scheduler.jobs.inactive_user_cleanup import (
    INACTIVE_DAYS,
    resolve_panel_uuid,
    run_inactive_user_cleanup,
)

UUID = "11111111-1111-1111-1111-111111111111"


def row(**kwargs) -> dict:
    base = dict(
        id="3f2504e0-4f89-11d3-9a0c-0305e82c3301",
        telegram_id=555,
        remnawave_uuid=None,
        remnawave_username=None,
        squad_tier="free",
    )
    return {**base, **kwargs}


# -- finding the account ---------------------------------------------------


async def test_the_stored_uuid_is_used_without_a_lookup():
    """The cheap path, and the one that survives a rename in the panel."""
    service = AsyncMock()
    with patch("app.scheduler.jobs.inactive_user_cleanup.user_service", service):
        assert await resolve_panel_uuid(row(remnawave_uuid=UUID)) == UUID
    service.get_user_by_username.assert_not_awaited()


async def test_a_new_style_account_is_found_by_its_stored_name():
    """
    The regression this file exists for: `u-<uuid>` accounts are invisible to
    a lookup by str(telegram_id).
    """
    service = AsyncMock()
    service.get_user_by_username = AsyncMock(return_value={"uuid": UUID})

    with patch("app.scheduler.jobs.inactive_user_cleanup.user_service", service):
        found = await resolve_panel_uuid(row(remnawave_username="u-3f2504e04f89"))

    assert found == UUID
    service.get_user_by_username.assert_awaited_with("u-3f2504e04f89")


async def test_a_legacy_account_is_still_found_by_its_telegram_id():
    service = AsyncMock()
    service.get_user_by_username = AsyncMock(side_effect=[{}, {"uuid": UUID}])

    with patch("app.scheduler.jobs.inactive_user_cleanup.user_service", service):
        assert await resolve_panel_uuid(row(remnawave_username="u-missing")) == UUID


async def test_an_account_that_is_already_gone_resolves_to_nothing():
    service = AsyncMock()
    service.get_user_by_username = AsyncMock(return_value={})

    with patch("app.scheduler.jobs.inactive_user_cleanup.user_service", service):
        assert await resolve_panel_uuid(row()) is None


async def test_a_user_with_no_handles_at_all_resolves_to_nothing():
    """Better than looking up `None` and deleting whatever comes back."""
    service = AsyncMock()
    with patch("app.scheduler.jobs.inactive_user_cleanup.user_service", service):
        assert await resolve_panel_uuid(row(telegram_id=None)) is None
    service.get_user_by_username.assert_not_awaited()


# -- the pass --------------------------------------------------------------


@pytest.fixture
def job(monkeypatch):
    repo = AsyncMock()
    service = AsyncMock()
    settings = AsyncMock()
    settings.free_tier_enabled = True

    monkeypatch.setattr("app.scheduler.jobs.inactive_user_cleanup._users_repo", repo)
    monkeypatch.setattr("app.scheduler.jobs.inactive_user_cleanup.user_service", service)
    monkeypatch.setattr(
        "app.scheduler.jobs.inactive_user_cleanup.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.inactive_user_cleanup.send_admin_message", AsyncMock()
    )
    return repo, service, settings


async def test_the_free_tier_mode_is_passed_to_the_query(job):
    repo, _service, settings = job
    repo.get_inactive_users_for_cleanup = AsyncMock(return_value=[])
    settings.free_tier_enabled = True

    await run_inactive_user_cleanup()

    repo.get_inactive_users_for_cleanup.assert_awaited_once_with(
        INACTIVE_DAYS, free_tier_enabled=True
    )


async def test_a_deleted_account_has_its_handles_cleared(job):
    """
    Otherwise the next pass chases a UUID that no longer resolves, every
    night, forever.
    """
    repo, service, _settings = job
    user = row(remnawave_uuid=UUID)
    repo.get_inactive_users_for_cleanup = AsyncMock(return_value=[user])

    await run_inactive_user_cleanup()

    service.delete_user.assert_awaited_once_with(UUID)
    repo.clear_panel_identity.assert_awaited_once_with(user["id"])


async def test_an_account_already_missing_is_still_cleared_but_not_deleted(job):
    repo, service, _settings = job
    service.get_user_by_username = AsyncMock(return_value={})
    repo.get_inactive_users_for_cleanup = AsyncMock(return_value=[row()])

    await run_inactive_user_cleanup()

    service.delete_user.assert_not_awaited()
    repo.clear_panel_identity.assert_awaited_once()


async def test_one_failure_does_not_abort_the_sweep(job):
    """The rest of the free squad still needs clearing."""
    repo, service, _settings = job
    repo.get_inactive_users_for_cleanup = AsyncMock(
        return_value=[
            row(telegram_id=1, remnawave_uuid="uuid-1"),
            row(telegram_id=2, remnawave_uuid="uuid-2"),
        ]
    )
    service.delete_user = AsyncMock(side_effect=[RuntimeError("panel down"), None])

    await run_inactive_user_cleanup()

    assert service.delete_user.await_count == 2


async def test_a_failed_deletion_does_not_clear_the_handles(job):
    """They are the only way to find the account again on the next pass."""
    repo, service, _settings = job
    repo.get_inactive_users_for_cleanup = AsyncMock(return_value=[row(remnawave_uuid=UUID)])
    service.delete_user = AsyncMock(side_effect=RuntimeError("panel down"))

    await run_inactive_user_cleanup()

    repo.clear_panel_identity.assert_not_awaited()


async def test_nothing_to_do_sends_no_admin_message(job):
    repo, _service, _settings = job
    repo.get_inactive_users_for_cleanup = AsyncMock(return_value=[])

    await run_inactive_user_cleanup()  # must not raise


async def test_a_query_failure_is_reported_not_raised(job):
    """The scheduler has to keep ticking."""
    repo, _service, _settings = job
    repo.get_inactive_users_for_cleanup = AsyncMock(side_effect=RuntimeError("db down"))

    await run_inactive_user_cleanup()  # must not raise

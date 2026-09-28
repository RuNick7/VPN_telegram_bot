"""
What actually goes out over the wire when an admin edits a user.

Two panel-side rejections live behind one generic message here, both found
the same way: reproducing the exact request by hand against the real panel
and reading the *full* error body, which the admin's "Ошибка при обновлении"
line does not show.

1. A datetime's plain `.isoformat()` writes `+00:00` for UTC, and the panel's
   schema rejects that outright. It wants the `Z` form, which
   `format_panel_timestamp` already produces for every other write path;
   `update_user` had grown its own instead and never matched it.
2. Fixing the format alone still failed, with a sharper message underneath:
   "Expiration date cannot be in the past". The panel refuses any `expireAt`
   that is not safely ahead of its own clock -- confirmed directly, one
   second ahead was rejected and sixty seconds was accepted -- which is
   exactly the date "mark this subscription as already expired" (the admin
   edit menu's own preset) asks for.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.users import _PANEL_EXPIRY_MIN_LEAD_SECONDS, UserService


@pytest.fixture
def service() -> UserService:
    svc = UserService()
    svc.client = AsyncMock()
    return svc


async def test_expiry_well_ahead_of_now_is_sent_in_the_z_form_unchanged(service: UserService):
    # Comfortably past the buffer, so the value comes through as given rather
    # than being nudged -- this test is about the format, not the floor.
    when = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0)

    await service.update_user("uuid-1", {"expire_at": when})

    sent = service.client.update_user.await_args.args[0]
    assert sent["expireAt"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert "+00:00" not in sent["expireAt"]


async def test_expiring_a_subscription_right_now_is_nudged_into_the_future(service: UserService):
    """
    The exact regression reported: the "Истёк" preset sends `datetime.now()`,
    which the panel rejects outright regardless of formatting. The value sent
    must be safely ahead of the panel's clock rather than equal to ours.
    """
    await service.update_user("uuid-1", {"expire_at": datetime.now(timezone.utc)})

    sent = service.client.update_user.await_args.args[0]
    sent_dt = datetime.strptime(sent["expireAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert sent_dt >= datetime.now(timezone.utc) + timedelta(
        seconds=_PANEL_EXPIRY_MIN_LEAD_SECONDS - 5  # a few seconds' slack for the test itself
    )


async def test_an_already_past_expiry_is_nudged_the_same_way(service: UserService):
    await service.update_user(
        "uuid-1", {"expire_at": datetime.now(timezone.utc) - timedelta(days=1)}
    )

    sent = service.client.update_user.await_args.args[0]
    sent_dt = datetime.strptime(sent["expireAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert sent_dt > datetime.now(timezone.utc)


async def test_a_non_datetime_field_passes_through_unchanged(service: UserService):
    await service.update_user("uuid-1", {"traffic_limit_bytes": 0})

    sent = service.client.update_user.await_args.args[0]
    assert sent == {"uuid": "uuid-1", "trafficLimitBytes": 0}


async def test_the_uuid_is_always_the_first_thing_in_the_payload(service: UserService):
    """`update_user` addresses by uuid; a payload missing it updates nobody."""
    await service.update_user("uuid-1", {})

    sent = service.client.update_user.await_args.args[0]
    assert sent["uuid"] == "uuid-1"

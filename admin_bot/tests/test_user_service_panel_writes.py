"""
What actually goes out over the wire when an admin edits a user.

The regression this guards: a datetime's plain `.isoformat()` writes `+00:00`
for UTC, and the panel's schema rejects that outright -- a bare "Validation
failed (status: 400)" with no field name to point at, from the admin trying to
expire someone's subscription through the edit menu. `format_panel_timestamp`
already produces the `Z` form every other write path uses; `update_user` had
grown its own instead and never matched it.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.users import UserService


@pytest.fixture
def service() -> UserService:
    svc = UserService()
    svc.client = AsyncMock()
    return svc


async def test_expiry_is_sent_in_the_z_form_the_panel_accepts(service: UserService):
    # Sub-second precision does not survive the round trip through
    # `format_panel_timestamp` (it goes by way of an epoch int), which is
    # fine -- nothing needs microsecond-precision expiry -- but means the
    # fixture has to be a whole second to compare exactly.
    when = datetime(2026, 8, 10, 10, 39, 48, tzinfo=timezone.utc)

    await service.update_user("uuid-1", {"expire_at": when})

    sent = service.client.update_user.await_args.args[0]
    assert sent["expireAt"] == "2026-08-10T10:39:48Z"


async def test_the_rejected_form_never_goes_out(service: UserService):
    """The exact string the panel's Zod schema was refusing."""
    when = datetime(2026, 8, 10, 10, 39, 48, 292762, tzinfo=timezone.utc)

    await service.update_user("uuid-1", {"expire_at": when})

    sent = service.client.update_user.await_args.args[0]
    assert "+00:00" not in sent["expireAt"]


async def test_a_non_datetime_field_passes_through_unchanged(service: UserService):
    await service.update_user("uuid-1", {"traffic_limit_bytes": 0})

    sent = service.client.update_user.await_args.args[0]
    assert sent == {"uuid": "uuid-1", "trafficLimitBytes": 0}


async def test_the_uuid_is_always_the_first_thing_in_the_payload(service: UserService):
    """`update_user` addresses by uuid; a payload missing it updates nobody."""
    await service.update_user("uuid-1", {})

    sent = service.client.update_user.await_args.args[0]
    assert sent["uuid"] == "uuid-1"

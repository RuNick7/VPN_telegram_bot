import pytest

from tgvpn_shared.db import AdminOperatorRepository, EventRepository


@pytest.fixture
def operators() -> AdminOperatorRepository:
    return AdminOperatorRepository()


@pytest.fixture
def events() -> EventRepository:
    return EventRepository()


async def test_admin_operator_create_and_role_update(operators: AdminOperatorRepository):
    assert await operators.exists(999) is False

    await operators.create(999, role="user")
    assert await operators.exists(999) is True
    assert (await operators.get_all_admins()) == []

    await operators.update_role(999, "admin")
    admins = await operators.get_all_admins()

    assert any(row["tg_id"] == 999 for row in admins)


async def test_log_event_does_not_raise(events: EventRepository):
    # This is the exact scenario that used to fail silently: bot_events was
    # never created by the old SQLite schema helper.
    await events.log_event(123, "some_callback", "menu")

"""
What the user-edit menu offers, and what it deliberately no longer does.

Two traffic budgets used to be settable from here: Remnawave's own
`trafficLimitBytes` and our per-cycle allowance. Whichever runs out first wins,
so the panel's figure could cut a user off well before the number an operator
had just typed -- and both buttons said "ГБ". An operator lowering gigabytes
picked the wrong one, watched the figure they meant sit unchanged, and put a
live account into LIMITED with nothing on any screen explaining why.
"""

from unittest.mock import AsyncMock

import pytest

from app.handlers.admin.users import edit
from app.handlers.admin.users.common import (
    create_expire_keyboard,
    edit_expire_keyboard,
    edit_field_keyboard,
)


def callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def labels(keyboard) -> list[str]:
    return [button.text for row in keyboard.inline_keyboard for button in row]


# -- the panel's competing limit -------------------------------------------


def test_the_panel_traffic_limit_is_not_offered():
    assert not any("traffic_limit_bytes" in data for data in callbacks(edit_field_keyboard()))


def test_gigabytes_means_exactly_one_thing_here():
    """
    Whatever the wording, only one button may be measured in ГБ per meaning.
    Two that read alike is the whole defect: the operator has to already know
    which is live to pick correctly, and the menu is what should tell them.
    """
    gigabyte_buttons = [text for text in labels(edit_field_keyboard()) if "ГБ" in text]
    assert gigabyte_buttons == ["📶 Трафик: ГБ в месяц"]


async def test_a_stale_button_is_answered_rather_than_obeyed():
    """
    An inline keyboard sent before the button was removed keeps working in
    Telegram's history forever. Accepting the tap and rejecting the typed value
    afterwards spends the operator's time to reach the same refusal.
    """
    callback = AsyncMock()
    callback.data = "admin:edit_user:field:traffic_limit_bytes"
    state = AsyncMock()

    await edit.choose_field(callback, state)

    state.set_state.assert_not_awaited()
    assert "Трафик: ГБ в месяц" in callback.message.answer.await_args.args[0]


# -- the allowance takes the panel limit with it ---------------------------


async def test_setting_the_allowance_clears_a_competing_panel_limit(monkeypatch):
    """
    Otherwise the number typed is not the number that applies: an account with
    0.1 GB left in the panel is cut off there however many gigabytes we grant.
    """
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(
        return_value={"trafficLimitBytes": 107374182, "status": "ACTIVE"}
    )
    monkeypatch.setattr(edit, "user_service", service)

    note = await edit._clear_panel_limit("uuid-1")

    service.update_user.assert_awaited_once_with("uuid-1", {"traffic_limit_bytes": 0})
    assert "0.10 ГБ" in note


async def test_an_account_with_no_panel_limit_is_left_alone(monkeypatch):
    """No write, and nothing added to a message about something else."""
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(return_value={"trafficLimitBytes": 0, "status": "ACTIVE"})
    monkeypatch.setattr(edit, "user_service", service)

    assert await edit._clear_panel_limit("uuid-1") == ""
    service.update_user.assert_not_awaited()


async def test_an_account_stuck_in_limited_is_let_back_in(monkeypatch):
    """
    Raising the limit does not by itself undo the status it caused: LIMITED is
    derived and can outlive the limit, leaving the account cut off for a reason
    that is no longer anywhere to be seen.
    """
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(
        return_value={"trafficLimitBytes": 107374182, "status": "LIMITED"}
    )
    monkeypatch.setattr(edit, "user_service", service)

    note = await edit._clear_panel_limit("uuid-1")

    service.update_user.assert_awaited_once_with(
        "uuid-1", {"traffic_limit_bytes": 0, "status": "ACTIVE"}
    )
    assert "LIMITED" in note


async def test_a_still_limited_account_is_freed_even_with_no_limit_left(monkeypatch):
    """The stale-status case on its own: limit already 0, status never followed."""
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(return_value={"trafficLimitBytes": 0, "status": "LIMITED"})
    monkeypatch.setattr(edit, "user_service", service)

    await edit._clear_panel_limit("uuid-1")
    assert service.update_user.await_args.args[1]["status"] == "ACTIVE"


async def test_a_deliberately_disabled_account_is_not_re_enabled(monkeypatch):
    """
    DISABLED is somebody's decision -- an operator's, or the middle of
    `disconnect_user`'s disable/drop/enable cycle. Flipping it to ACTIVE from
    here would quietly undo either one.
    """
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(
        return_value={"trafficLimitBytes": 107374182, "status": "DISABLED"}
    )
    monkeypatch.setattr(edit, "user_service", service)

    await edit._clear_panel_limit("uuid-1")
    assert "status" not in service.update_user.await_args.args[1]


async def test_an_account_with_no_panel_profile_is_not_looked_up(monkeypatch):
    """A website account may have none, and the allowance is still ours to set."""
    service = AsyncMock()
    monkeypatch.setattr(edit, "user_service", service)

    assert await edit._clear_panel_limit(None) == ""
    service.get_user_by_uuid.assert_not_awaited()


async def test_a_panel_failure_does_not_lose_the_allowance(monkeypatch):
    """
    The allowance is already stored by the time this runs. Raising here would
    surface as "❌ Ошибка при обновлении" over a write that succeeded, and the
    operator would set it again.
    """
    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(side_effect=RuntimeError("panel down"))
    monkeypatch.setattr(edit, "user_service", service)

    note = await edit._clear_panel_limit("uuid-1")
    assert "panel down" in note


async def test_the_allowance_survives_a_panel_that_will_not_answer(monkeypatch):
    """
    End to end: the number the operator typed is written to our database even
    when the panel half fails, and the failure is still told rather than
    swallowed.
    """
    lte = AsyncMock()
    lte.set_free_gb_override_by_user_id = AsyncMock(return_value=True)
    monkeypatch.setattr(edit, "lte_repo", lte)

    service = AsyncMock()
    service.get_user_by_uuid = AsyncMock(side_effect=RuntimeError("panel down"))
    monkeypatch.setattr(edit, "user_service", service)

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"row_id": "row-1", "user_uuid": "uuid-1"})
    message = AsyncMock()

    await edit._apply_db_only_update(message, state, "lte_free_gb", "50")

    lte.set_free_gb_override_by_user_id.assert_awaited_once_with("row-1", 50)
    said = message.answer.await_args.args[0]
    assert "50 ГБ/мес" in said
    assert "panel down" in said


# -- ending a subscription -------------------------------------------------


def test_the_edit_form_can_end_a_subscription_now():
    """"Платная подписка закончилась" as a button rather than a known trick."""
    assert "admin:edit_user:expire:expired" in callbacks(edit_expire_keyboard())


def test_the_creation_form_cannot():
    """An account created already expired connects to nothing; nobody means that."""
    assert "admin:new_user:expire:expired" not in callbacks(create_expire_keyboard())


async def test_ending_it_writes_a_date_that_is_not_in_the_future(monkeypatch):
    import time

    applied = {}

    async def fake_apply(message, state, payload):
        applied.update(payload)

    monkeypatch.setattr(edit, "apply_update", fake_apply)
    callback = AsyncMock()
    callback.data = "admin:edit_user:expire:expired"

    await edit.choose_expire_preset(callback, AsyncMock())

    assert applied["expire_at"].timestamp() <= time.time() + 1


async def test_typing_zero_days_is_still_accepted(monkeypatch):
    """
    The route that worked all along and nothing advertised. It stays working:
    an operator who learned it should not find it broken by the new button.
    """
    applied = {}

    async def fake_apply(message, state, payload):
        applied.update(payload)

    monkeypatch.setattr(edit, "apply_update", fake_apply)
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"field": "expire_at"})
    message = AsyncMock()
    message.text = "0"

    await edit.receive_value(message, state)

    assert "expire_at" in applied


@pytest.mark.parametrize("preset", ["forever", "month", "week"])
async def test_the_other_presets_still_work(preset, monkeypatch):
    applied = {}

    async def fake_apply(message, state, payload):
        applied.update(payload)

    monkeypatch.setattr(edit, "apply_update", fake_apply)
    callback = AsyncMock()
    callback.data = f"admin:edit_user:expire:{preset}"

    await edit.choose_expire_preset(callback, AsyncMock())
    assert "expire_at" in applied

"""Host editing feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from app.services.hosts import host_service
from app.states.admin import HostEditState

router = Router(name="admin_hosts_edit")


@router.callback_query(F.data.startswith("admin:hosts:edit:"))
async def start_edit_host(callback: CallbackQuery, state: FSMContext):
    """Start host editing flow."""
    host_id = callback.data.split(":")[-1]
    await state.update_data(host_id=host_id)
    await callback.message.answer("📝 Введите поле для редактирования (name, ip):")
    await state.set_state(HostEditState.field)
    await callback.answer()

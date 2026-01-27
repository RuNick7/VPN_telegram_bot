"""Host creation feature."""

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from app.services.hosts import host_service
from app.states.admin import HostCreateState

router = Router(name="admin_hosts_create")


@router.callback_query(lambda c: c.data and c.data.startswith("admin:hosts:create"))
async def start_create_host(callback: CallbackQuery, state: FSMContext):
    """Start host creation flow."""
    await callback.message.answer("📝 Введите название хоста:")
    await state.set_state(HostCreateState.name)
    await callback.answer()


@router.message(HostCreateState.name)
async def process_host_name(message: Message, state: FSMContext):
    """Process host name."""
    await state.update_data(name=message.text)
    await message.answer("🖥️ Введите ID узла:")
    await state.set_state(HostCreateState.node_id)

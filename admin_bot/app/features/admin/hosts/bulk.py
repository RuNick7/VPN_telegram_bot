"""Bulk host operations feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from app.services.hosts import host_service

router = Router(name="admin_hosts_bulk")


@router.callback_query(F.data == "admin:hosts:bulk_create")
async def start_bulk_create_hosts(callback: CallbackQuery, state: FSMContext):
    """Start bulk host creation flow."""
    await callback.message.answer(
        "📋 Введите список хостов в формате:\n"
        "name1:ip1\n"
        "name2:ip2\n"
        "..."
    )
    # Set a custom state for bulk creation
    await state.set_state("bulk_hosts")
    await callback.answer()

"""Bulk operations for internal squad users."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

router = Router(name="admin_squads_internal_users_bulk")


@router.callback_query(F.data.startswith("admin:squads:internal:users:bulk:"))
async def start_bulk_internal_users(callback: CallbackQuery, state: FSMContext):
    """Start bulk user operations for internal squad."""
    squad_id = callback.data.split(":")[-1]
    await state.update_data(squad_id=squad_id)
    await callback.message.answer(
        "📋 Введите список пользователей (Telegram IDs или usernames):\n"
        "Каждая строка - один пользователь"
    )
    await state.set_state("bulk_internal_users")
    await callback.answer()

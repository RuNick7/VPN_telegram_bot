"""Admin menu handlers."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from app.keyboards.admin import get_admin_menu_keyboard

router = Router(name="admin_menu")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    await message.answer(
        "🔐 Админ-панель",
        reply_markup=get_admin_menu_keyboard()
    )


@router.callback_query(F.data == "admin:menu")
async def callback_admin_menu(callback: CallbackQuery):
    """Handle admin menu callback."""
    await callback.message.edit_text(
        "🔐 Админ-панель",
        reply_markup=get_admin_menu_keyboard()
    )
    await callback.answer()

"""Admin menu handlers."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from app.keyboards.admin import get_admin_menu_keyboard
from app.services.access import check_admin_access

router = Router(name="admin_menu")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return

    await message.answer(
        "🔐 Админ-панель",
        reply_markup=get_admin_menu_keyboard()
    )


@router.callback_query(F.data == "admin:menu")
async def callback_admin_menu(callback: CallbackQuery):
    """Handle admin menu callback."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 Админ-панель",
        reply_markup=get_admin_menu_keyboard()
    )
    await callback.answer()

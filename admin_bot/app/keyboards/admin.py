"""Admin keyboard layouts."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin main menu keyboard."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Новый пользователь", callback_data="admin:new_user")],
            [InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data="admin:edit_user")],
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="admin:delete_user")],
            [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin:promo_create")],
            [InlineKeyboardButton(text="🗑️ Удалить промокод", callback_data="admin:promo_delete")],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="➕ Добавить хост", callback_data="admin:host_quick_add")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")]
        ]
    )
    return keyboard

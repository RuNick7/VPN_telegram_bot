"""Admin keyboard layouts."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin main menu keyboard."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Новый пользователь", callback_data="admin:new_user")],
            [InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data="admin:edit_user")],
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="admin:delete_user")],
            [InlineKeyboardButton(text="🔎 Поиск пользователя", callback_data="admin:user_search")],
            [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin:promo_create")],
            [InlineKeyboardButton(text="🗑️ Удалить промокод", callback_data="admin:promo_delete")],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast")],
            # Host creation and deletion are gone from this menu on purpose.
            # A host is infrastructure, edited once in a while and with more
            # context than a chat window gives; the panel is where that
            # belongs. The handlers still exist and still work if their
            # callbacks are reached, so nothing was deleted that would need
            # rewriting to bring back.
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")]
        ]
    )
    return keyboard

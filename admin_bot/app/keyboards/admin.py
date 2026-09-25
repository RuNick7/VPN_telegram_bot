"""Admin keyboard layouts."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config.settings import settings


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin main menu keyboard."""
    # Offered only while tickets are being taken: with SUPPORT_ENABLED off
    # the queue can only ever be empty.
    support = (
        [[InlineKeyboardButton(text="🆘 Поддержка", callback_data="admin:support")]]
        if settings.support_enabled
        else []
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=support + [
            [InlineKeyboardButton(text="👤 Новый пользователь", callback_data="admin:new_user")],
            [InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data="admin:edit_user")],
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="admin:delete_user")],
            [InlineKeyboardButton(text="🔎 Поиск пользователя", callback_data="admin:user_search")],
            [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin:promo_create")],
            [InlineKeyboardButton(text="🗑️ Удалить промокод", callback_data="admin:promo_delete")],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast")],
            [
                InlineKeyboardButton(text="🎁 Подарки", callback_data="admin:gifts"),
                InlineKeyboardButton(text="💳 Платежи", callback_data="admin:payments"),
            ],
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

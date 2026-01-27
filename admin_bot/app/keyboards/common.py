"""Common keyboard layouts."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Главное меню")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_back_button() -> InlineKeyboardMarkup:
    """Back button inline keyboard."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ]
    )
    return keyboard

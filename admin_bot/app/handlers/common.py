"""Common handlers."""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer("👋 Добро пожаловать в KairaVPN Admin Bot!")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "📖 Доступные команды:\n"
        "/start - Начать работу\n"
        "/admin - Админ-панель\n"
        "/tickets - Обращения в поддержку, ждущие ответа\n"
        "/help - Показать справку\n\n"
        "Чтобы ответить на обращение, ответьте (reply) на его карточку."
    )

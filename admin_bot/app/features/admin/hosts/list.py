"""Host list feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.services.hosts import host_service

router = Router(name="admin_hosts_list")


@router.callback_query(F.data == "admin:hosts")
async def list_hosts(callback: CallbackQuery):
    """List all hosts."""
    try:
        hosts = await host_service.list_hosts()
        if not hosts:
            await callback.message.answer("📭 Хосты не найдены.")
            await callback.answer()
            return

        text = "🌐 Список хостов:\n\n"
        for host in hosts:
            text += f"• {host.get('name', 'N/A')} - {host.get('ip', 'N/A')}\n"

        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()

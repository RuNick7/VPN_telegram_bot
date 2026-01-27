"""Node list feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.services.nodes import node_service

router = Router(name="admin_nodes_list")


@router.callback_query(F.data == "admin:nodes")
async def list_nodes(callback: CallbackQuery):
    """List all nodes."""
    try:
        nodes = await node_service.list_nodes()
        if not nodes:
            await callback.message.answer("📭 Узлы не найдены.")
            await callback.answer()
            return

        text = "🖥️ Список узлов:\n\n"
        for node in nodes:
            text += f"• {node.get('name', 'N/A')} ({node.get('host', 'N/A')})\n"

        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()

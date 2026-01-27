"""Node actions feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.services.nodes import node_service

router = Router(name="admin_nodes_actions")


@router.callback_query(F.data.startswith("admin:nodes:delete:"))
async def delete_node(callback: CallbackQuery):
    """Delete a node."""
    node_id = callback.data.split(":")[-1]
    try:
        await node_service.delete_node(node_id)
        await callback.message.answer(f"✅ Узел {node_id} удален.")
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()

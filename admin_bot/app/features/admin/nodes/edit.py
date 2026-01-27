"""Node editing feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from app.services.nodes import node_service
from app.states.admin import NodeEditState

router = Router(name="admin_nodes_edit")


@router.callback_query(F.data.startswith("admin:nodes:edit:"))
async def start_edit_node(callback: CallbackQuery, state: FSMContext):
    """Start node editing flow."""
    node_id = callback.data.split(":")[-1]
    await state.update_data(node_id=node_id)
    await callback.message.answer("📝 Введите поле для редактирования (name, host, port):")
    await state.set_state(NodeEditState.field)
    await callback.answer()

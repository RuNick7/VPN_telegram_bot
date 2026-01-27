"""Node creation feature."""

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from app.services.nodes import node_service
from app.states.admin import NodeCreateState

router = Router(name="admin_nodes_create")


@router.callback_query(lambda c: c.data and c.data.startswith("admin:nodes:create"))
async def start_create_node(callback: CallbackQuery, state: FSMContext):
    """Start node creation flow."""
    await callback.message.answer("📝 Введите название узла:")
    await state.set_state(NodeCreateState.name)
    await callback.answer()


@router.message(NodeCreateState.name)
async def process_node_name(message: Message, state: FSMContext):
    """Process node name."""
    await state.update_data(name=message.text)
    await message.answer("🌐 Введите хост:")
    await state.set_state(NodeCreateState.host)

"""Internal squad management feature."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.services.squads import squad_service

router = Router(name="admin_squads_internal")


@router.callback_query(F.data == "admin:squads:internal")
async def list_internal_squads(callback: CallbackQuery):
    """List internal squads."""
    try:
        squads = await squad_service.list_squads(squad_type="internal")
        if not squads:
            await callback.message.answer("📭 Внутренние отряды не найдены.")
            await callback.answer()
            return

        text = "👥 Внутренние отряды:\n\n"
        for squad in squads:
            text += f"• {squad.get('name', 'N/A')}\n"

        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()

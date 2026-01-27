"""Admin broadcast handlers."""

import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.services.access import check_admin_access
from app.services.subscription_db import get_all_telegram_ids
from app.states.admin import BroadcastState

router = Router(name="admin_broadcast")

BATCH_SIZE = 25
PAUSE_BETWEEN_BATCHES = 1.0  # seconds
PAUSE_BETWEEN_MESSAGES = 0.05

def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Запустить", callback_data="admin:broadcast:send"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast:cancel"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(BroadcastState.content)
    await callback.message.answer(
        "Отправьте сообщение для рассылки.\n"
        "Можно текст или фото/видео с подписью.",
        reply_markup=_menu_keyboard(),
    )
    await callback.answer()


@router.message(BroadcastState.content)
async def capture_broadcast_content(message: Message, state: FSMContext):
    """Capture broadcast content (text/photo/video)."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption or ""
        await state.update_data(kind="photo", file_id=file_id, caption=caption)
        await state.set_state(BroadcastState.confirm)
        await message.answer("Готово. Запустить рассылку фото?", reply_markup=_confirm_keyboard())
        return

    if message.video:
        file_id = message.video.file_id
        caption = message.caption or ""
        await state.update_data(kind="video", file_id=file_id, caption=caption)
        await state.set_state(BroadcastState.confirm)
        await message.answer("Готово. Запустить рассылку видео?", reply_markup=_confirm_keyboard())
        return

    if message.text:
        await state.update_data(kind="text", text=message.text)
        await state.set_state(BroadcastState.confirm)
        await message.answer("Готово. Запустить рассылку текста?", reply_markup=_confirm_keyboard())
        return

    await message.answer("❌ Отправьте текст или фото/видео с подписью.")


@router.callback_query(F.data == "admin:broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast."""
    await state.clear()
    await callback.message.answer("Рассылка отменена.", reply_markup=_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast:send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Send broadcast to all telegram_id from DB."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    data = await state.get_data()
    kind = data.get("kind")
    ids = await get_all_telegram_ids()

    if not ids:
        await callback.message.answer("❌ В базе нет пользователей.", reply_markup=_menu_keyboard())
        await state.clear()
        await callback.answer()
        return

    sent = 0
    failed = 0
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        for tg_id in batch:
            try:
                if kind == "text":
                    await callback.bot.send_message(tg_id, data.get("text", ""))
                elif kind == "photo":
                    await callback.bot.send_photo(tg_id, data.get("file_id"), caption=data.get("caption"))
                elif kind == "video":
                    await callback.bot.send_video(tg_id, data.get("file_id"), caption=data.get("caption"))
                else:
                    failed += 1
                    continue
                sent += 1
                await asyncio.sleep(PAUSE_BETWEEN_MESSAGES)
            except Exception:
                failed += 1
        await asyncio.sleep(PAUSE_BETWEEN_BATCHES)

    await callback.message.answer(
        f"✅ Рассылка завершена.\n"
        f"Отправлено: {sent}\n"
        f"Ошибки: {failed}",
        reply_markup=_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()

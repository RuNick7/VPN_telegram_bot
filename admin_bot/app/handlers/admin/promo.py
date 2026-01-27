"""Admin promo code handlers."""

import secrets
import string

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.services.access import check_admin_access
from app.services.subscription_db import insert_promo_code, delete_promo_code
from app.states.admin import PromoCreateState, PromoDeleteState

router = Router(name="admin_promo")


def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]]
    )


def _promo_code_source_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Вручную", callback_data="admin:promo_create:manual"),
                InlineKeyboardButton(text="🎲 Сгенерировать", callback_data="admin:promo_create:generate"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _promo_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 gift", callback_data="admin:promo_create:type:gift"),
                InlineKeyboardButton(text="📅 days", callback_data="admin:promo_create:type:days"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _one_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да (1 раз)", callback_data="admin:promo_create:one_time:1"),
                InlineKeyboardButton(text="♻️ Нет (много)", callback_data="admin:promo_create:one_time:0"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _generate_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.callback_query(F.data == "admin:promo_create")
async def promo_create_start(callback: CallbackQuery, state: FSMContext):
    """Start promo code creation flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "Как задать код промокода?",
        reply_markup=_promo_code_source_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create:manual")
async def promo_create_manual(callback: CallbackQuery, state: FSMContext):
    """Manual promo code input."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.set_state(PromoCreateState.code)
    await callback.message.answer("Введите код промокода:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create:generate")
async def promo_create_generate(callback: CallbackQuery, state: FSMContext):
    """Generate promo code."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    code = _generate_code()
    await state.update_data(code=code)
    await state.set_state(PromoCreateState.promo_type)
    await callback.message.answer(
        f"Сгенерирован код: {code}\nВыберите тип промокода:",
        reply_markup=_promo_type_keyboard(),
    )
    await callback.answer()


@router.message(PromoCreateState.code)
async def promo_create_code(message: Message, state: FSMContext):
    """Handle manual code input."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    code = (message.text or "").strip()
    if not code:
        await message.answer("❌ Код не может быть пустым.")
        return

    await state.update_data(code=code)
    await state.set_state(PromoCreateState.promo_type)
    await message.answer("Выберите тип промокода:", reply_markup=_promo_type_keyboard())


@router.callback_query(F.data.startswith("admin:promo_create:type:"))
async def promo_create_type(callback: CallbackQuery, state: FSMContext):
    """Handle promo type selection."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    promo_type = callback.data.split(":")[-1]
    await state.update_data(promo_type=promo_type)
    await state.set_state(PromoCreateState.value)
    await callback.message.answer("Введите значение (дни):", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(PromoCreateState.value)
async def promo_create_value(message: Message, state: FSMContext):
    """Handle promo value input."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите целое число (дни).")
        return

    await state.update_data(value=int(text))
    await state.set_state(PromoCreateState.one_time)
    await message.answer("Одноразовый промокод?", reply_markup=_one_time_keyboard())


@router.callback_query(F.data.startswith("admin:promo_create:one_time:"))
async def promo_create_one_time(callback: CallbackQuery, state: FSMContext):
    """Handle one_time selection."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    one_time = int(callback.data.split(":")[-1])
    data = await state.get_data()
    code = data.get("code")
    promo_type = data.get("promo_type")
    value = data.get("value")
    if not (code and promo_type and value is not None):
        await callback.message.answer("❌ Не хватает данных для создания промокода.")
        await state.clear()
        await callback.answer()
        return

    try:
        await insert_promo_code(code=code, promo_type=promo_type, value=value, one_time=one_time)
        await callback.message.answer(
            f"✅ Промокод создан:\n"
            f"code: {code}\n"
            f"type: {promo_type}\n"
            f"value: {value}\n"
            f"one_time: {one_time}",
            reply_markup=_menu_keyboard(),
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
    finally:
        await state.clear()
        await callback.answer()


@router.callback_query(F.data == "admin:promo_delete")
async def promo_delete_start(callback: CallbackQuery, state: FSMContext):
    """Start promo deletion flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.set_state(PromoDeleteState.code)
    await callback.message.answer("Введите код промокода для удаления:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(PromoDeleteState.code)
async def promo_delete_code(message: Message, state: FSMContext):
    """Delete promo code."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    code = (message.text or "").strip()
    if not code:
        await message.answer("❌ Код не может быть пустым.")
        return

    try:
        deleted = await delete_promo_code(code)
        if deleted:
            await message.answer(f"✅ Промокод {code} удален.", reply_markup=_menu_keyboard())
        else:
            await message.answer(f"❌ Промокод {code} не найден.", reply_markup=_menu_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
    finally:
        await state.clear()

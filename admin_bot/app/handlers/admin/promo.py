"""Admin promo code handlers."""

import html
import secrets
import string
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from tgvpn_shared.db import PromoRepository
from app.handlers.admin.pagination import (
    PagedView,
    parse_page,
    picker_keyboard,
    prompt_page_input,
    register_view,
)
from app.states.admin import PromoCreateState, PromoDeleteState

router = Router(name="admin_promo")
_promo = PromoRepository()

LIST_PREFIX = "admin:promo_del:list"
LIST_GOTO = "admin:promo_del:list:goto"
PAGE_SIZE = 8

# Telegram rejects callback data over 64 bytes, and a promo code is
# operator-supplied text of no fixed length. A code too long to address is left
# without a button rather than sent and rejected -- `picker_keyboard` drops any
# item whose callback comes back empty, and typing the code still deletes it.
CALLBACK_LIMIT = 64


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
    await state.clear()
    await callback.message.answer(
        "Как задать код промокода?",
        reply_markup=_promo_code_source_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create:manual")
async def promo_create_manual(callback: CallbackQuery, state: FSMContext):
    """Manual promo code input."""
    await state.set_state(PromoCreateState.code)
    await callback.message.answer("Введите код промокода:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create:generate")
async def promo_create_generate(callback: CallbackQuery, state: FSMContext):
    """Generate promo code."""
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
    promo_type = callback.data.split(":")[-1]
    await state.update_data(promo_type=promo_type)
    await state.set_state(PromoCreateState.value)
    await callback.message.answer("Введите значение (дни):", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(PromoCreateState.value)
async def promo_create_value(message: Message, state: FSMContext):
    """Handle promo value input."""
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
        await _promo.insert_promo_code(
            code=code,
            promo_type=promo_type,
            value=value,
            one_time=one_time,
            # Whoever pressed the button. The delete list is the only place a
            # code is ever reviewed, and "who made this" is the question that
            # decides whether it is safe to remove.
            creator_id=callback.from_user.id if callback.from_user else None,
        )
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


# -- the promo code list ---------------------------------------------------


def creator_of(row: dict) -> str:
    """
    Who made this code, by whatever handle they have.

    Two kinds of author reach this table. An operator creating one in the admin
    bot is a Telegram ID and usually has no customer row, so the bare ID is all
    there is -- and it still names them. A gift is bought by a customer, who
    may have signed up on the website and have only an address. Codes from
    before the author was recorded have neither, and say so rather than
    inventing one.
    """
    if row.get("creator_tag"):
        return f"@{row['creator_tag']}"
    if row.get("creator_email"):
        return str(row["creator_email"])
    telegram_id = row.get("creator_telegram_id") or row.get("creator_id")
    return f"tg:{telegram_id}" if telegram_id else "—"


def promo_label(row: dict) -> str:
    """A code as one button: what it grants and whether it is spent."""
    used = int(row.get("used_count") or 0)
    spent = " ✔️" if used and row.get("one_time") else (f" ×{used}" if used else "")
    return f"{row['code']} — {row.get('value', 0)} дн.{spent}"


def promo_callback(row: dict) -> str | None:
    data = f"admin:promo_del:pick:{row['code']}"
    return data if len(data.encode()) <= CALLBACK_LIMIT else None


def format_promo_page(rows: list[dict], page: int, total: int) -> str:
    """The page as text, because a button can't hold what an operator needs."""
    lines = [f"🎟 <b>Промокоды</b> — всего {total}, страница {page}\n"]
    for row in rows:
        used = int(row.get("used_count") or 0)
        created = row.get("created_at")
        when = created.strftime("%d.%m.%Y") if isinstance(created, datetime) else "—"
        flags = ["одноразовый" if row.get("one_time") else "многоразовый"]
        if not row.get("is_active"):
            flags.append("выключен")
        lines.append(
            f"<code>{html.escape(str(row['code']))}</code> — "
            f"{row.get('value', 0)} дн. ({html.escape(str(row.get('type') or '—'))})\n"
            f"  {', '.join(flags)} · использован: {used}\n"
            f"  создал: {html.escape(creator_of(row))} · {when}"
        )
    return "\n".join(lines)


async def render_promo_list(target: Message, page: int, size: int, edit: bool) -> None:
    total = await _promo.count_promo_codes()
    rows = [dict(row) for row in await _promo.list_promo_codes_page(size, (max(1, page) - 1) * size)]
    if not rows:
        await target.answer("📭 Промокодов нет.", reply_markup=_menu_keyboard())
        return

    text = format_promo_page(rows, page, total)
    keyboard = picker_keyboard(
        rows,
        label=promo_label,
        item_callback=promo_callback,
        prefix=LIST_PREFIX,
        page=page,
        total=total,
        size=size,
        goto_callback_data=LIST_GOTO,
    )
    if edit:
        await target.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


VIEW = register_view(
    PagedView(
        name="promo",
        size=PAGE_SIZE,
        render=render_promo_list,
        count=_promo.count_promo_codes,
    )
)


def _delete_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Показать список", callback_data=LIST_PREFIX),
                InlineKeyboardButton(text="✍️ Ввести код", callback_data="admin:promo_del:manual"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _confirm_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:promo_del:yes:{code}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data=LIST_PREFIX)],
        ]
    )


# -- deletion --------------------------------------------------------------


@router.callback_query(F.data == "admin:promo_delete")
async def promo_delete_start(callback: CallbackQuery, state: FSMContext):
    """Start promo deletion flow."""
    await state.clear()
    await callback.message.answer(
        "Как выбрать промокод для удаления?", reply_markup=_delete_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_del:manual")
async def promo_delete_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoDeleteState.code)
    await callback.message.answer("Введите код промокода для удаления:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == LIST_PREFIX)
async def promo_list(callback: CallbackQuery):
    try:
        await render_promo_list(callback.message, 1, PAGE_SIZE, edit=False)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data == LIST_GOTO)
async def promo_list_goto(callback: CallbackQuery, state: FSMContext):
    await prompt_page_input(callback.message, state, view=VIEW)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{LIST_PREFIX}:"))
async def promo_list_page(callback: CallbackQuery):
    try:
        await render_promo_list(callback.message, parse_page(callback.data), PAGE_SIZE, edit=True)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_del:pick:"))
async def promo_delete_pick(callback: CallbackQuery):
    """
    Confirm before deleting, because there is no undo and no audit trail.

    A code is a bearer credential: the row is all that records what was
    promised, so a mis-tap on a list of eight similar-looking codes destroys
    it with nothing to restore from.
    """
    code = callback.data.split(":", 3)[-1]
    row = await _promo.get_promo_by_code(code) or await _promo.get_promo_by_code(code.upper())
    if row is None:
        await callback.message.answer("❌ Промокод не найден — возможно, уже удалён.")
        await callback.answer()
        return

    used = await _promo.has_any_usage(code)
    await callback.message.answer(
        f"Удалить промокод <code>{html.escape(code)}</code>?\n"
        f"Даёт: {row['value']} дн. ({row['type']})\n"
        + ("⚠️ Он уже был использован — история активации останется.\n" if used else ""),
        reply_markup=_confirm_keyboard(code),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_del:yes:"))
async def promo_delete_confirmed(callback: CallbackQuery):
    code = callback.data.split(":", 3)[-1]
    try:
        deleted = await _promo.delete_promo_code(code)
        await callback.message.answer(
            f"✅ Промокод {code} удалён." if deleted else f"❌ Промокод {code} не найден.",
            reply_markup=_delete_start_keyboard(),
        )
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(PromoDeleteState.code)
async def promo_delete_code(message: Message, state: FSMContext):
    """Delete promo code."""
    code = (message.text or "").strip()
    if not code:
        await message.answer("❌ Код не может быть пустым.")
        return

    try:
        deleted = await _promo.delete_promo_code(code)
        if deleted:
            await message.answer(f"✅ Промокод {code} удален.", reply_markup=_menu_keyboard())
        else:
            await message.answer(f"❌ Промокод {code} не найден.", reply_markup=_menu_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
    finally:
        await state.clear()

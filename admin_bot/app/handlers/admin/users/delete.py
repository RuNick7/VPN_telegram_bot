"""Delete a user from the panel and from our database."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.admin.pagination import (
    PagedView,
    parse_page,
    picker_keyboard,
    prompt_page_input,
    register_view,
)
from app.handlers.admin.users.common import (
    HANDLE_PROMPT,
    count_users,
    delete_start_keyboard,
    delete_user_everywhere,
    fetch_users_page,
    find_db_row,
    find_panel_user,
    telegram_id_of,
)
from app.services.users import user_service
from app.states.admin import UserDeleteState

router = Router(name="admin_users_delete")

PREFIX = "admin:del:list"
GOTO = "admin:del:list:goto"
PAGE_SIZE = 10


async def render(target: Message, page: int, size: int, edit: bool) -> None:
    users, total = await fetch_users_page(page, size)
    if not users:
        await target.answer("📭 Пользователи не найдены.")
        return
    keyboard = picker_keyboard(
        users,
        label=lambda user: str(user.get("username", "unknown")),
        item_callback=lambda user: f"admin:del:uuid:{user['uuid']}" if user.get("uuid") else None,
        prefix=PREFIX,
        page=page,
        total=total,
        size=size,
        goto_callback_data=GOTO,
    )
    text = "Выберите пользователя для удаления:"
    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


VIEW = register_view(PagedView(name="delete", size=PAGE_SIZE, render=render, count=count_users))


@router.callback_query(F.data == "admin:delete_user")
async def start_delete(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Выберите способ удаления пользователя:", reply_markup=delete_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:del:username")
async def prompt_username(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserDeleteState.username)
    await callback.message.answer(HANDLE_PROMPT)
    await callback.answer()


@router.callback_query(F.data == PREFIX)
async def show_list(callback: CallbackQuery):
    try:
        await render(callback.message, 1, PAGE_SIZE, edit=False)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data == GOTO)
async def goto_prompt(callback: CallbackQuery, state: FSMContext):
    await prompt_page_input(callback.message, state, view=VIEW)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{PREFIX}:"))
async def show_page(callback: CallbackQuery):
    try:
        await render(callback.message, parse_page(callback.data), PAGE_SIZE, edit=True)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:del:uuid:"))
async def delete_from_list(callback: CallbackQuery):
    user_uuid = callback.data.rsplit(":", 1)[-1]
    try:
        user = await user_service.get_user_by_uuid(user_uuid)
        username = user.get("username")
        if not username:
            await callback.message.answer("❌ Не удалось получить пользователя.")
        else:
            where = await delete_user_everywhere(
                user_uuid, str(username), telegram_id_of(user, str(username))
            )
            await callback.message.answer(
                f"✅ Пользователь {username} удален из: {where or 'нигде'}."
            )
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка при удалении: {exc}")
    await callback.answer()


@router.message(UserDeleteState.username)
async def delete_by_username(message: Message, state: FSMContext):
    """
    Delete whoever the admin named, by any handle they have.

    A Telegram ID, an email, a @tag, our UUID or the panel username -- the
    same set every other flow accepts. The row is deleted by our own id when
    we found one, which is the only handle a website account has.
    """
    needle = (message.text or "").strip()
    try:
        row = await find_db_row(needle)
        user, name = await find_panel_user(needle, row)
        user_uuid = (user or {}).get("uuid")
        note = "" if user_uuid else "\nℹ️ Аккаунт в Remnawave не найден."

        where = await delete_user_everywhere(
            user_uuid,
            name or needle,
            telegram_id_of(user or {}, name or needle),
            row_id=str(row["id"]) if row else None,
        )
        if not where:
            await message.answer("❌ Пользователь не найден ни в Remnawave, ни в БД.")
            return
        await message.answer(f"✅ Пользователь {name or needle} удален из: {where}.{note}")
    except Exception as exc:
        await message.answer(f"❌ Ошибка при удалении: {exc}")
    finally:
        await state.clear()

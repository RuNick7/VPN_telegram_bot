"""Edit an existing panel user's fields."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    DATE_FOREVER,
    count_users,
    edit_again_keyboard,
    edit_expire_keyboard,
    edit_field_keyboard,
    edit_start_keyboard,
    expire_at_of,
    fetch_users_page,
    parse_iso_datetime,
    telegram_id_of,
    users_repo,
)
from app.services.users import user_service
from app.states.admin import UserEditState

router = Router(name="admin_users_edit")

PREFIX = "admin:edit_user:list"
GOTO = "admin:edit_user:list:goto"
PAGE_SIZE = 10

BYTES_PER_GB = 1024**3


async def render(target: Message, page: int, size: int, edit: bool) -> None:
    users, total = await fetch_users_page(page, size)
    if not users:
        await target.answer("📭 Пользователи не найдены.")
        return
    keyboard = picker_keyboard(
        users,
        label=lambda user: str(user.get("username", "unknown")),
        item_callback=lambda user: (
            f"admin:edit_user:select_uuid:{user['uuid']}" if user.get("uuid") else None
        ),
        prefix=PREFIX,
        page=page,
        total=total,
        size=size,
        goto_callback_data=GOTO,
    )
    if edit:
        await target.edit_text("Выберите пользователя:", reply_markup=keyboard)
    else:
        await target.answer("Выберите пользователя:", reply_markup=keyboard)


VIEW = register_view(PagedView(name="edit", size=PAGE_SIZE, render=render, count=count_users))


async def _open_field_menu(target: Message, state: FSMContext, user: dict, username: str) -> None:
    """Remember which user is being edited and offer the field picker."""
    await state.update_data(
        user_uuid=user.get("uuid"),
        username=username,
        telegram_id=telegram_id_of(user, username),
        expire_at=expire_at_of(user),
    )
    await state.set_state(UserEditState.field)
    await target.answer(
        f"Пользователь: {username}\nВыберите поле для редактирования:",
        reply_markup=edit_field_keyboard(),
    )


async def apply_update(
    message: Message,
    state: FSMContext,
    payload: dict,
    new_telegram_id: int | None = None,
) -> None:
    """
    Push one field change to the panel, mirroring it into our database.

    Expiry and telegram_id are the two fields we also store, so they are
    written through to the subscription row; everything else is panel-only.
    """
    data = await state.get_data()
    user_uuid = data.get("user_uuid")
    telegram_id = data.get("telegram_id")
    if not user_uuid:
        await message.answer("❌ Не выбран пользователь.")
        await state.clear()
        return

    try:
        await user_service.update_user(user_uuid, payload)

        if "expire_at" in payload and telegram_id:
            await users_repo.upsert_subscription_expire(
                telegram_id=telegram_id,
                subscription_ends=int(payload["expire_at"].timestamp()),
            )
        if new_telegram_id and telegram_id:
            expire_at = data.get("expire_at")
            parsed = parse_iso_datetime(expire_at) if isinstance(expire_at, str) else None
            await users_repo.upsert_subscription_telegram_id(
                old_telegram_id=telegram_id,
                new_telegram_id=new_telegram_id,
                subscription_ends=int(parsed.timestamp()) if parsed else None,
            )
            await state.update_data(telegram_id=new_telegram_id)

        await message.answer("✅ Пользователь обновлен.", reply_markup=edit_again_keyboard())
        await state.set_state(UserEditState.field)
    except Exception as exc:
        await message.answer(f"❌ Ошибка при обновлении: {exc}")
        await state.clear()


# -- entry points ----------------------------------------------------------


@router.callback_query(F.data == "admin:edit_user")
async def start_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Выберите способ поиска пользователя:", reply_markup=edit_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:edit_user:username")
async def prompt_username(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserEditState.username)
    await callback.message.answer("Введите username пользователя для редактирования:")
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


@router.callback_query(F.data.startswith("admin:edit_user:select_uuid:"))
async def select_from_list(callback: CallbackQuery, state: FSMContext):
    user_uuid = callback.data.rsplit(":", 1)[-1]
    try:
        user = await user_service.get_user_by_uuid(user_uuid)
        username = user.get("username")
        if not username:
            await callback.message.answer("❌ Не удалось получить пользователя.")
        else:
            await _open_field_menu(callback.message, state, user, str(username))
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.message(UserEditState.username)
async def select_by_username(message: Message, state: FSMContext):
    username = (message.text or "").strip()
    try:
        user = await user_service.get_user_by_username(username)
        if not user.get("uuid"):
            await message.answer("❌ Пользователь не найден.")
            return
        await _open_field_menu(message, state, user, username)
    except Exception as exc:
        await message.answer(f"❌ Ошибка: {exc}")


# -- field selection and values -------------------------------------------


@router.callback_query(F.data.startswith("admin:edit_user:field:"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.rsplit(":", 1)[-1]
    await state.update_data(field=field)
    await state.set_state(UserEditState.value)

    prompts = {
        "traffic_limit_bytes": "Введите лимит трафика в ГБ (например 1 или 1.5):",
        "hwid_device_limit": "Введите лимит устройств HWID:",
    }
    if field == "expire_at":
        await callback.message.answer(
            "Выберите новый срок действия:", reply_markup=edit_expire_keyboard()
        )
    else:
        await callback.message.answer(prompts.get(field, "Введите новое значение:"))
    await callback.answer()


@router.callback_query(F.data == "admin:edit_user:back")
async def back_to_field_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("user_uuid"):
        await callback.message.answer(
            "Выберите способ поиска пользователя:", reply_markup=edit_start_keyboard()
        )
        await state.set_state(UserEditState.username)
    else:
        await callback.message.answer(
            f"Пользователь: {data.get('username', 'unknown')}\nВыберите поле для редактирования:",
            reply_markup=edit_field_keyboard(),
        )
        await state.set_state(UserEditState.field)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:expire:"))
async def choose_expire_preset(callback: CallbackQuery, state: FSMContext):
    action = callback.data.rsplit(":", 1)[-1]
    presets = {
        "forever": DATE_FOREVER,
        "month": datetime.now(timezone.utc) + timedelta(days=30),
        "week": datetime.now(timezone.utc) + timedelta(days=7),
    }
    if action in presets:
        await apply_update(callback.message, state, {"expire_at": presets[action]})
    else:
        await callback.message.answer("Введите количество дней до окончания:")
    await callback.answer()


@router.message(UserEditState.value)
async def receive_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    text = (message.text or "").strip()

    if field == "traffic_limit_bytes":
        try:
            gigabytes = float(text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число в ГБ (например 1 или 1.5).")
            return
        await apply_update(message, state, {"traffic_limit_bytes": int(gigabytes * BYTES_PER_GB)})
        return

    if field == "hwid_device_limit":
        if not text.isdigit():
            await message.answer("❌ Введите числовой лимит устройств.")
            return
        await apply_update(message, state, {"hwidDeviceLimit": int(text)})
        return

    if field == "expire_at":
        if not text.isdigit():
            await message.answer("❌ Введите количество дней числом.")
            return
        await apply_update(
            message, state, {"expire_at": datetime.now(timezone.utc) + timedelta(days=int(text))}
        )
        return

    if field == "tag":
        await apply_update(message, state, {"tag": text})
        return

    await message.answer("❌ Неизвестное поле.")

"""Admin user handlers."""

import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import html
import httpx
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.services.access import check_admin_access
from app.services.users import user_service
from app.services.subscription_db import (
    upsert_subscription_expire,
    upsert_subscription_telegram_id,
    update_subscription_referred_people,
    delete_subscription_user,
    delete_subscription_user_by_username,
    get_subscription_rows_by_telegram_id,
)
from app.states.admin import (
    UserCreateState,
    UserEditState,
    UserDeleteState,
    UserListPageState,
    UserSearchState,
)

router = Router(name="admin_users")

USERNAME_RE = re.compile(r"^\d{6,20}$")
DATE_FOREVER = datetime(2099, 1, 1, tzinfo=timezone.utc)
PAGE_MODE_STATS = "stats"
PAGE_MODE_EDIT = "edit"
PAGE_MODE_DELETE = "delete"


def _skip_keyboard(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"admin:new_user:skip:{step}")]
        ]
    )


def _expire_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="♾️ Навсегда", callback_data="admin:new_user:expire:forever"),
                InlineKeyboardButton(text="🗓️ Месяц", callback_data="admin:new_user:expire:month")
            ],
            [InlineKeyboardButton(text="📅 Неделя", callback_data="admin:new_user:expire:week")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin:new_user:expire:skip")]
        ]
    )


def _edit_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Показать список", callback_data="admin:edit_user:list"),
                InlineKeyboardButton(text="✍️ Ввести username", callback_data="admin:edit_user:username")
            ]
        ]
    )

def _delete_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Показать список", callback_data="admin:del:list"),
                InlineKeyboardButton(text="✍️ Ввести username", callback_data="admin:del:username")
            ]
        ]
    )


def _edit_field_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Срок (expire)", callback_data="admin:edit_user:field:expire_at")
            ],
            [
                InlineKeyboardButton(text="Лимит (ГБ)", callback_data="admin:edit_user:field:traffic_limit_bytes"),
                InlineKeyboardButton(text="Tag", callback_data="admin:edit_user:field:tag")
            ],
            [
                InlineKeyboardButton(text="HWID лимит", callback_data="admin:edit_user:field:hwid_device_limit"),
                InlineKeyboardButton(text="Рефералы", callback_data="admin:edit_user:field:referred_people"),
            ]
        ]
    )


def _edit_again_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Изменить ещё", callback_data="admin:edit_user:back")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _pagination_keyboard(
    prefix: str,
    page: int,
    total: int,
    size: int,
    *,
    goto_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    max_page = max(1, (total + size - 1) // size)
    prev_page = max(1, page - 1)
    next_page = min(max_page, page + 1)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{prev_page}"),
                InlineKeyboardButton(
                    text=f"{page}/{max_page}",
                    callback_data=goto_callback_data or "noop",
                ),
                InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{next_page}")
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]
        ]
    )


def _users_list_keyboard(users: list[dict], page: int, total: int, size: int) -> InlineKeyboardMarkup:
    max_page = max(1, (total + size - 1) // size)
    prev_page = max(1, page - 1)
    next_page = min(max_page, page + 1)
    rows = [
        [
            InlineKeyboardButton(
                text=user.get("username", "unknown"),
                callback_data=f"admin:edit_user:select_uuid:{user.get('uuid')}"
            )
        ]
        for user in users if user.get("uuid")
    ]
    rows.append(
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"admin:edit_user:list:{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="admin:edit_user:list:goto"),
            InlineKeyboardButton(text="➡️", callback_data=f"admin:edit_user:list:{next_page}")
        ]
    )
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _users_delete_list_keyboard(users: list[dict], page: int, total: int, size: int) -> InlineKeyboardMarkup:
    max_page = max(1, (total + size - 1) // size)
    prev_page = max(1, page - 1)
    next_page = min(max_page, page + 1)
    rows = [
        [
            InlineKeyboardButton(
                text=user.get("username", "unknown"),
                callback_data=f"admin:del:uuid:{user.get('uuid')}"
            )
        ]
        for user in users if user.get("uuid")
    ]
    rows.append(
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"admin:del:list:{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="admin:del:list:goto"),
            InlineKeyboardButton(text="➡️", callback_data=f"admin:del:list:{next_page}")
        ]
    )
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _edit_expire_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="♾️ Навсегда", callback_data="admin:edit_user:expire:forever"),
                InlineKeyboardButton(text="🗓️ Месяц", callback_data="admin:edit_user:expire:month")
            ],
            [InlineKeyboardButton(text="📅 Неделя", callback_data="admin:edit_user:expire:week")],
            [InlineKeyboardButton(text="✍️ Ввести дни", callback_data="admin:edit_user:expire:custom")]
        ]
    )


def _days_left(expire_at: str) -> str:
    try:
        value = expire_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
    except Exception:
        return "-"
    if dt.year >= 2099:
        return "∞"
    now = datetime.now(timezone.utc)
    delta = dt.date() - now.date()
    return str(delta.days)


def _format_user_line(user: dict, name_w: int, tg_w: int, days_w: int) -> str:
    username = user.get("username", "unknown")
    telegram_id = user.get("telegramId") or user.get("telegram_id") or "-"
    expire_at = user.get("expireAt") or user.get("expire_at") or ""
    days_left = _days_left(expire_at) if expire_at else "-"
    return f"{username:<{name_w}} | {str(telegram_id):<{tg_w}} | {days_left:>{days_w}}"


def _is_online(user: dict) -> bool:
    return bool(user.get("onlineAt") or user.get("online_at"))


def _fmt_ts_utc(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def _build_user_search_report(telegram_id: int, rem_user: dict | None, db_rows: list[dict]) -> str:
    lines: list[str] = [f"🔎 Поиск пользователя: <code>{telegram_id}</code>", ""]

    if rem_user:
        username = rem_user.get("username", "-")
        uuid = rem_user.get("uuid", "-")
        tag = rem_user.get("tag", "-")
        traffic = rem_user.get("trafficLimitBytes") or rem_user.get("traffic_limit_bytes")
        online = "да" if _is_online(rem_user) else "нет"
        expire_at = rem_user.get("expireAt") or rem_user.get("expire_at") or "-"
        days_left = _days_left(expire_at) if isinstance(expire_at, str) else "-"
        lines.extend(
            [
                "<b>Remnawave</b>",
                f"username: <code>{html.escape(str(username))}</code>",
                f"uuid: <code>{html.escape(str(uuid))}</code>",
                f"tag: <code>{html.escape(str(tag))}</code>",
                f"online: {online}",
                f"expire_at: <code>{html.escape(str(expire_at))}</code>",
                f"days_left: <code>{html.escape(str(days_left))}</code>",
                f"traffic_limit_bytes: <code>{html.escape(str(traffic if traffic is not None else '-'))}</code>",
                "",
            ]
        )
    else:
        lines.extend(["<b>Remnawave</b>", "не найден", ""])

    lines.append(f"<b>subscription.db</b> (записей: {len(db_rows)})")
    if not db_rows:
        lines.append("не найден")
    else:
        for row in db_rows:
            lines.extend(
                [
                    f"• id=<code>{row.get('id', '-')}</code>"
                    f" ends=<code>{_fmt_ts_utc(row.get('subscription_ends'))}</code>"
                    f" reminded=<code>{row.get('reminded', '-')}</code>"
                    f" stage=<code>{row.get('nurture_stage', '-')}</code>",
                    f"  tag=<code>{html.escape(str(row.get('telegram_tag') or '-'))}</code>"
                    f" referred=<code>{row.get('referred_people', 0)}</code>"
                    f" gifted=<code>{row.get('gifted_subscriptions', 0)}</code>",
                ]
            )

    return "\n".join(lines)


async def _prompt_page_input(
    target: Message,
    state: FSMContext,
    *,
    mode: str,
    size: int,
) -> None:
    await state.update_data(page_mode=mode, page_size=size)
    await state.set_state(UserListPageState.page_input)
    await target.answer("Введите номер страницы:")


async def _render_stats_page(target: Message, page: int, size: int, *, edit: bool) -> None:
    response = await user_service.list_users(page=page, size=size)
    data = response.get("response", {})
    users = data.get("users", [])
    total = data.get("total", len(users))
    online = sum(1 for user in users if _is_online(user))

    usernames = [user.get("username", "unknown") for user in users]
    telegram_ids = [str(user.get("telegramId") or user.get("telegram_id") or "-") for user in users]
    days_values = [_days_left(user.get("expireAt") or user.get("expire_at") or "") for user in users]

    name_w = max(8, *(len(value) for value in usernames)) if users else 8
    tg_w = max(11, *(len(value) for value in telegram_ids)) if users else 11
    days_w = max(4, *(len(value) for value in days_values)) if users else 4

    header = f"{'username':<{name_w}} | {'telegram_id':<{tg_w}} | {'days':>{days_w}}"
    divider = "-" * len(header)
    lines = [
        "📊 Статистика:",
        f"Всего пользователей: {total}",
        f"Онлайн (из выборки): {online}",
        "",
        "Список пользователей (страница):" if edit else "Список пользователей (первые 50):",
        header,
        divider,
    ]
    lines.extend(_format_user_line(user, name_w, tg_w, days_w) for user in users)
    safe_text = html.escape("\n".join(lines))
    kb = _pagination_keyboard(
        "admin:stats:page",
        page,
        total,
        size,
        goto_callback_data="admin:stats:goto",
    )
    if edit:
        await target.edit_text(f"<pre>{safe_text}</pre>", reply_markup=kb)
    else:
        await target.answer(f"<pre>{safe_text}</pre>", reply_markup=kb)


async def _render_edit_users_page(target: Message, page: int, size: int, *, edit: bool) -> None:
    response = await user_service.list_users(page=page, size=size)
    users = response.get("response", {}).get("users", [])
    total = response.get("response", {}).get("total", len(users))
    if not users:
        await target.answer("📭 Пользователи не найдены.")
        return
    if edit:
        await target.edit_text("Выберите пользователя:", reply_markup=_users_list_keyboard(users, page, total, size))
    else:
        await target.answer("Выберите пользователя:", reply_markup=_users_list_keyboard(users, page, total, size))


async def _render_delete_users_page(target: Message, page: int, size: int, *, edit: bool) -> None:
    response = await user_service.list_users(page=page, size=size)
    users = response.get("response", {}).get("users", [])
    total = response.get("response", {}).get("total", len(users))
    if not users:
        await target.answer("📭 Пользователи не найдены.")
        return
    if edit:
        await target.edit_text(
            "Выберите пользователя для удаления:",
            reply_markup=_users_delete_list_keyboard(users, page, total, size),
        )
    else:
        await target.answer(
            "Выберите пользователя для удаления:",
            reply_markup=_users_delete_list_keyboard(users, page, total, size),
        )


@router.callback_query(F.data == "admin:new_user")
async def callback_new_user(callback: CallbackQuery, state: FSMContext):
    """Start new user creation flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.set_state(UserCreateState.username)
    await callback.message.answer(
        "Введите username для нового пользователя.\n"
        "Требования: только цифры (Telegram ID), минимум 6 символов."
    )
    await callback.answer()


@router.callback_query(F.data == "admin:edit_user")
async def callback_edit_user(callback: CallbackQuery, state: FSMContext):
    """Start edit user flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "Выберите способ поиска пользователя:",
        reply_markup=_edit_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:delete_user")
async def callback_delete_user(callback: CallbackQuery, state: FSMContext):
    """Start delete user flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "Выберите способ удаления пользователя:",
        reply_markup=_delete_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:user_search")
async def callback_user_search(callback: CallbackQuery, state: FSMContext):
    """Start search user flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    await state.set_state(UserSearchState.telegram_id)
    await callback.message.answer("Введите telegram_id (он же username) для поиска:")
    await callback.answer()


@router.message(UserSearchState.telegram_id)
async def handle_user_search_input(message: Message, state: FSMContext):
    """Search user in Remnawave and subscription DB by telegram_id."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Введите telegram_id числом.")
        return

    telegram_id = int(raw)
    rem_user: dict | None = None
    try:
        found = await user_service.get_user_by_username(raw)
        rem_user = found if found else None
    except Exception as e:
        await message.answer(f"⚠️ Ошибка запроса к Remnawave: {str(e)}")

    try:
        db_rows = await get_subscription_rows_by_telegram_id(telegram_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка чтения subscription.db: {str(e)}")
        await state.clear()
        return

    report = _build_user_search_report(telegram_id, rem_user, db_rows)
    await message.answer(report, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "admin:del:username")
async def delete_user_by_username_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    await state.set_state(UserDeleteState.username)
    await callback.message.answer("Введите username пользователя для удаления:")
    await callback.answer()


@router.callback_query(F.data == "admin:del:list")
async def delete_user_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    try:
        page = 1
        size = 10
        await _render_delete_users_page(callback.message, page, size, edit=False)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.callback_query(F.data == "admin:del:list:goto")
async def delete_user_list_goto_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    await _prompt_page_input(callback.message, state, mode=PAGE_MODE_DELETE, size=10)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:del:list:"))
async def delete_user_list_page(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    try:
        page = int(callback.data.split(":")[-1])
        size = 10
        await _render_delete_users_page(callback.message, page, size, edit=True)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.callback_query(F.data.startswith("admin:del:uuid:"))
async def delete_user_select(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    user_uuid = callback.data.split(":")[-1]
    try:
        user_response = await user_service.get_user_by_uuid(user_uuid)
        user = user_response.get("response", user_response)
        username = user.get("username")
        telegram_id = user.get("telegramId") or user.get("telegram_id")
        if not telegram_id and username and str(username).isdigit():
            telegram_id = int(username)
        if not username:
            await callback.message.answer("❌ Не удалось получить пользователя.")
            await callback.answer()
            return

        deleted_in_panel = False
        deleted_in_db = False

        await user_service.delete_user(user_uuid)
        deleted_in_panel = True

        if telegram_id:
            deleted_in_db = await delete_subscription_user(int(telegram_id))
        else:
            deleted_in_db = await delete_subscription_user_by_username(username)

        where = []
        if deleted_in_panel:
            where.append("Remnawave")
        if deleted_in_db:
            where.append("БД")
        where_text = " и ".join(where) if where else "нигде"
        await callback.message.answer(f"✅ Пользователь {username} удален из: {where_text}.")
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при удалении: {str(e)}")
        await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def callback_stats(callback: CallbackQuery):
    """Show users stats and list."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    try:
        page = 1
        size = 20
        await _render_stats_page(callback.message, page, size, edit=False)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.callback_query(F.data == "admin:stats:goto")
async def callback_stats_goto_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    await _prompt_page_input(callback.message, state, mode=PAGE_MODE_STATS, size=20)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:stats:page:"))
async def callback_stats_page(callback: CallbackQuery):
    """Paginated stats view."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[-1])
        size = 20
        await _render_stats_page(callback.message, page, size, edit=True)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.callback_query(F.data == "admin:edit_user:list")
async def edit_user_list(callback: CallbackQuery, state: FSMContext):
    """Show users list."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    try:
        page = 1
        size = 10
        await _render_edit_users_page(callback.message, page, size, edit=False)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.callback_query(F.data == "admin:edit_user:list:goto")
async def edit_user_list_goto_prompt(callback: CallbackQuery, state: FSMContext):
    """Ask admin for page number in edit list."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    await _prompt_page_input(callback.message, state, mode=PAGE_MODE_EDIT, size=10)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:list:"))
async def edit_user_list_page(callback: CallbackQuery, state: FSMContext):
    """Paginated users list for editing."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[-1])
        size = 10
        await _render_edit_users_page(callback.message, page, size, edit=True)
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.message(UserListPageState.page_input)
async def handle_users_page_input(message: Message, state: FSMContext):
    """Handle manual page number input for list views."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Введите номер страницы числом.")
        return

    page = int(raw)
    if page < 1:
        await message.answer("❌ Номер страницы должен быть больше 0.")
        return

    data = await state.get_data()
    mode = data.get("page_mode")
    size = int(data.get("page_size") or 10)

    try:
        response = await user_service.list_users(page=1, size=size)
        total = response.get("response", {}).get("total", 0)
        max_page = max(1, (total + size - 1) // size)
        if page > max_page:
            await message.answer(f"❌ Такой страницы нет. Доступно: 1..{max_page}.")
            return

        if mode == PAGE_MODE_STATS:
            await _render_stats_page(message, page, size, edit=False)
        elif mode == PAGE_MODE_EDIT:
            await _render_edit_users_page(message, page, size, edit=False)
        elif mode == PAGE_MODE_DELETE:
            await _render_delete_users_page(message, page, size, edit=False)
        else:
            await message.answer("❌ Неизвестный тип списка. Попробуйте снова из меню.")
            return
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        return
    finally:
        await state.clear()


@router.callback_query(F.data == "admin:edit_user:username")
async def edit_user_by_username_prompt(callback: CallbackQuery, state: FSMContext):
    """Ask for username input."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.set_state(UserEditState.username)
    await callback.message.answer("Введите username пользователя для редактирования:")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:select_uuid:"))
async def edit_user_select(callback: CallbackQuery, state: FSMContext):
    """Select user from list."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    user_uuid = callback.data.split(":")[-1]
    try:
        user_response = await user_service.get_user_by_uuid(user_uuid)
        user = user_response.get("response", user_response)
        username = user.get("username")
        telegram_id = user.get("telegramId") or user.get("telegram_id")
        if not telegram_id and username and str(username).isdigit():
            telegram_id = int(username)
        expire_at = user.get("expireAt") or user.get("expire_at")
        if not username:
            await callback.message.answer("❌ Не удалось получить пользователя.")
            await callback.answer()
            return
        await state.update_data(
            user_uuid=user_uuid,
            username=username,
            telegram_id=telegram_id,
            expire_at=expire_at
        )
        await state.set_state(UserEditState.field)
        await callback.message.answer(
            f"Пользователь: {username}\n"
            "Выберите поле для редактирования:",
            reply_markup=_edit_field_keyboard()
        )
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
        await callback.answer()


@router.message(UserEditState.username)
async def edit_user_username_input(message: Message, state: FSMContext):
    """Handle manual username input."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    username = (message.text or "").strip()
    try:
        user = await user_service.get_user_by_username(username)
        user_uuid = user.get("uuid")
        telegram_id = user.get("telegramId") or user.get("telegram_id")
        if not telegram_id and username.isdigit():
            telegram_id = int(username)
        expire_at = user.get("expireAt") or user.get("expire_at")
        if not user_uuid:
            await message.answer("❌ Пользователь не найден.")
            return
        await state.update_data(
            user_uuid=user_uuid,
            username=username,
            telegram_id=telegram_id,
            expire_at=expire_at
        )
        await state.set_state(UserEditState.field)
        await message.answer(
            f"Пользователь: {username}\n"
            "Выберите поле для редактирования:",
            reply_markup=_edit_field_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(UserDeleteState.username)
async def delete_user_by_username(message: Message, state: FSMContext):
    """Delete user by username in panel and DB."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    username = (message.text or "").strip()
    deleted_in_panel = False
    deleted_in_db = False
    panel_note = ""

    try:
        user = await user_service.get_user_by_username(username)
        user_uuid = user.get("uuid")
        telegram_id = user.get("telegramId") or user.get("telegram_id")
        if not telegram_id and username.isdigit():
            telegram_id = int(username)

        if user_uuid:
            await user_service.delete_user(user_uuid)
            deleted_in_panel = True
        else:
            panel_note = "Пользователь не найден в Remnawave."

        if telegram_id:
            deleted_in_db = await delete_subscription_user(int(telegram_id))
        else:
            deleted_in_db = await delete_subscription_user_by_username(username)

        if not deleted_in_db and not deleted_in_panel:
            await message.answer("❌ Пользователь не найден ни в Remnawave, ни в БД.")
            return

        where = []
        if deleted_in_panel:
            where.append("Remnawave")
        if deleted_in_db:
            where.append("БД")
        where_text = " и ".join(where)
        note = f"\nℹ️ {panel_note}" if panel_note else ""
        await message.answer(f"✅ Пользователь {username} удален из: {where_text}.{note}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при удалении: {str(e)}")
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("admin:edit_user:field:"))
async def edit_user_field(callback: CallbackQuery, state: FSMContext):
    """Select field to edit."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return

    field = callback.data.split(":")[-1]
    await state.update_data(field=field)
    await state.set_state(UserEditState.value)

    if field == "expire_at":
        await callback.message.answer(
            "Выберите новый срок действия:",
            reply_markup=_edit_expire_keyboard()
        )
    elif field == "traffic_limit_bytes":
        await callback.message.answer("Введите лимит трафика в ГБ (например 1 или 1.5):")
    elif field == "hwid_device_limit":
        await callback.message.answer("Введите лимит устройств HWID:")
    elif field == "referred_people":
        await callback.message.answer("Введите количество рефералов (целое число >= 0):")
    else:
        await callback.message.answer("Введите новое значение:")
    await callback.answer()


@router.callback_query(F.data == "admin:edit_user:back")
async def edit_user_back(callback: CallbackQuery, state: FSMContext):
    """Return to edit field selection for current user."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    data = await state.get_data()
    if not data.get("user_uuid"):
        await callback.message.answer(
            "Выберите способ поиска пользователя:",
            reply_markup=_edit_start_keyboard()
        )
        await state.set_state(UserEditState.username)
    else:
        await callback.message.answer(
            f"Пользователь: {data.get('username', 'unknown')}\n"
            "Выберите поле для редактирования:",
            reply_markup=_edit_field_keyboard()
        )
        await state.set_state(UserEditState.field)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:expire:"))
async def edit_user_expire(callback: CallbackQuery, state: FSMContext):
    """Handle expire preset for edit."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return

    action = callback.data.split(":")[-1]
    if action == "forever":
        expire_at = DATE_FOREVER
        await _apply_user_update(callback.message, state, {"expire_at": expire_at})
    elif action == "month":
        expire_at = datetime.now(timezone.utc) + timedelta(days=30)
        await _apply_user_update(callback.message, state, {"expire_at": expire_at})
    elif action == "week":
        expire_at = datetime.now(timezone.utc) + timedelta(days=7)
        await _apply_user_update(callback.message, state, {"expire_at": expire_at})
    else:
        await callback.message.answer("Введите количество дней до окончания:")
    await callback.answer()


@router.message(UserEditState.value)
async def edit_user_value_input(message: Message, state: FSMContext):
    """Handle new value input for selected field."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    data = await state.get_data()
    field = data.get("field")
    text = (message.text or "").strip()

    if field == "traffic_limit_bytes":
        try:
            gb_value = float(text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число в ГБ (например 1 или 1.5).")
            return
        bytes_value = int(gb_value * 1024**3)
        await _apply_user_update(message, state, {"traffic_limit_bytes": bytes_value})
        return

    if field == "hwid_device_limit":
        if not text.isdigit():
            await message.answer("❌ Введите числовой лимит устройств.")
            return
        await _apply_user_update(message, state, {"hwidDeviceLimit": int(text)})
        return

    if field == "expire_at":
        if not text.isdigit():
            await message.answer("❌ Введите количество дней числом.")
            return
        expire_at = datetime.now(timezone.utc) + timedelta(days=int(text))
        await _apply_user_update(message, state, {"expire_at": expire_at})
        return

    if field == "referred_people":
        if not text.isdigit():
            await message.answer("❌ Введите целое число >= 0.")
            return
        await _apply_user_update(message, state, {"referred_people": int(text)})
        return


    if field == "tag":
        await _apply_user_update(message, state, {"tag": text})
        return

    await message.answer("❌ Неизвестное поле.")


async def _apply_user_update(
    message: Message,
    state: FSMContext,
    payload: dict,
    new_telegram_id: int | None = None
):
    """Apply user update and report result."""
    data = await state.get_data()
    user_uuid = data.get("user_uuid")
    telegram_id = data.get("telegram_id")
    if not user_uuid:
        await message.answer("❌ Не выбран пользователь.")
        await state.clear()
        return

    try:
        if "referred_people" in payload:
            resolved_telegram_id = telegram_id
            if not resolved_telegram_id:
                username = str(data.get("username") or "").strip()
                if username.isdigit():
                    resolved_telegram_id = int(username)
            if not resolved_telegram_id:
                await message.answer("❌ Не удалось определить telegram_id для обновления рефералов.")
                await state.clear()
                return

            updated = await update_subscription_referred_people(
                int(resolved_telegram_id),
                int(payload["referred_people"]),
            )
            if not updated:
                await message.answer(
                    "❌ Запись в subscription.db не найдена для этого пользователя."
                )
                await state.clear()
                return
            await message.answer(
                "✅ Количество рефералов обновлено в subscription.db.",
                reply_markup=_edit_again_keyboard(),
            )
            await state.set_state(UserEditState.field)
            return

        response = await user_service.update_user(user_uuid, payload)
        if "expire_at" in payload and telegram_id:
            await upsert_subscription_expire(
                telegram_id=telegram_id,
                subscription_ends=payload["expire_at"]
            )
        if new_telegram_id and telegram_id:
            expire_at_value = data.get("expire_at")
            expire_dt = _parse_iso_datetime(expire_at_value) if isinstance(expire_at_value, str) else None
            await upsert_subscription_telegram_id(
                old_telegram_id=telegram_id,
                new_telegram_id=new_telegram_id,
                subscription_ends=expire_dt
            )
            await state.update_data(telegram_id=new_telegram_id)
        await message.answer(
            "✅ Пользователь обновлен.",
            reply_markup=_edit_again_keyboard()
        )
        await state.set_state(UserEditState.field)
    except Exception as e:
        await message.answer(f"❌ Ошибка при обновлении: {str(e)}")
        await state.clear()


@router.message(UserCreateState.username)
async def handle_new_user_username(message: Message, state: FSMContext):
    """Handle username input and create user."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    username = (message.text or "").strip()
    if not USERNAME_RE.fullmatch(username):
        await message.answer(
            "❌ Некорректный username. Нужны только цифры (Telegram ID), минимум 6 символов."
        )
        return

    await state.update_data(username=username)
    await state.set_state(UserCreateState.expire_at)
    await message.answer(
        "Выберите срок действия пользователя:",
        reply_markup=_expire_keyboard()
    )


@router.callback_query(F.data.startswith("admin:new_user:expire:"))
async def set_expire(callback: CallbackQuery, state: FSMContext):
    """Handle expire selection."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    action = callback.data.split(":")[-1]
    if action == "forever":
        expire_at = DATE_FOREVER
    elif action == "month":
        expire_at = datetime.now(timezone.utc) + timedelta(days=30)
    elif action == "week":
        expire_at = datetime.now(timezone.utc) + timedelta(days=7)
    else:
        expire_at = datetime.now(timezone.utc) + timedelta(days=1)

    await state.update_data(expire_at=expire_at)
    await state.set_state(UserCreateState.traffic_limit_bytes)
    await callback.message.answer(
        "Введите лимит трафика в ГБ (например: 1 или 1.5):",
        reply_markup=_skip_keyboard("traffic")
    )
    await callback.answer()


@router.message(UserCreateState.traffic_limit_bytes)
async def handle_traffic_limit(message: Message, state: FSMContext):
    """Handle traffic limit input."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    text = (message.text or "").strip()
    try:
        gb_value = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число в ГБ (например 1 или 1.5) или нажмите Пропустить.")
        return
    bytes_value = int(gb_value * 1024**3)
    await state.update_data(traffic_limit_bytes=bytes_value)
    await state.set_state(UserCreateState.tag)
    await message.answer("Введите tag (или пропустите):", reply_markup=_skip_keyboard("tag"))


@router.callback_query(F.data == "admin:new_user:skip:traffic")
async def skip_traffic(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    await state.set_state(UserCreateState.tag)
    await callback.message.answer("Введите tag (или пропустите):", reply_markup=_skip_keyboard("tag"))
    await callback.answer()


@router.message(UserCreateState.tag)
async def handle_tag(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    tag = (message.text or "").strip()
    if tag:
        await state.update_data(tag=tag)
    await state.set_state(UserCreateState.telegram_id)
    await message.answer("Введите telegram_id (или пропустите):", reply_markup=_skip_keyboard("telegram_id"))


@router.callback_query(F.data == "admin:new_user:skip:tag")
async def skip_tag(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    await state.set_state(UserCreateState.telegram_id)
    await callback.message.answer("Введите telegram_id (или пропустите):", reply_markup=_skip_keyboard("telegram_id"))
    await callback.answer()


@router.message(UserCreateState.telegram_id)
async def handle_telegram_id(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой telegram_id или нажмите Пропустить.")
        return
    await state.update_data(telegram_id=int(text))
    await state.set_state(UserCreateState.hwid_device_limit)
    await message.answer("Введите лимит устройств HWID (или пропустите):", reply_markup=_skip_keyboard("hwid"))


@router.callback_query(F.data == "admin:new_user:skip:telegram_id")
async def skip_telegram_id(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    await state.set_state(UserCreateState.hwid_device_limit)
    await callback.message.answer("Введите лимит устройств HWID (или пропустите):", reply_markup=_skip_keyboard("hwid"))
    await callback.answer()


@router.message(UserCreateState.hwid_device_limit)
async def handle_hwid(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой лимит устройств или нажмите Пропустить.")
        return
    await state.update_data(hwid_device_limit=int(text))
    await _finalize_user_create(message, state)


@router.callback_query(F.data == "admin:new_user:skip:hwid")
async def skip_hwid(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return
    await _finalize_user_create(callback.message, state)
    await callback.answer()


async def _finalize_user_create(message: Message, state: FSMContext):
    data = await state.get_data()
    telegram_id = data.get("telegram_id") or message.from_user.id
    try:
        user = await user_service.create_user(
            username=data["username"],
            expire_at=data.get("expire_at"),
            traffic_limit_bytes=data.get("traffic_limit_bytes"),
            tag=data.get("tag"),
            telegram_id=telegram_id,
            hwid_device_limit=data.get("hwid_device_limit")
        )
        subscription_url = user.get("subscription_url") or user.get("subscriptionUrl")
        user_uuid = user.get("uuid")
        await message.answer(
            "✅ Пользователь создан.\n"
            f"Username: {user.get('username')}\n"
            f"UUID: {user_uuid}\n"
            f"Sub URL: {subscription_url}"
        )
    except socket.gaierror:
            await message.answer(
                "❌ Ошибка DNS: не удалось разрешить адрес панели.\n"
                "Проверь `REMNAWAVE_BASE_URL` и доступность хоста."
            )
    except httpx.RequestError as e:
        if "nodename nor servname" in str(e).lower():
            base_url = user_service.client.base_url
            host = urlparse(base_url).hostname or base_url
            await message.answer(
                "❌ Ошибка DNS при подключении к панели.\n"
                f"Хост: {host}\n"
                "Проверь `REMNAWAVE_BASE_URL`, DNS и доступность хоста."
            )
        else:
            await message.answer(f"❌ Ошибка сети: {str(e)}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании пользователя: {str(e)}")
    finally:
        await state.clear()

"""Paginated user statistics table."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.admin.pagination import (
    PagedView,
    nav_keyboard,
    parse_page,
    prompt_page_input,
    register_view,
)
from app.handlers.admin.users.common import (
    count_users,
    days_left,
    expire_at_of,
    fetch_users_page,
    is_online,
)

router = Router(name="admin_users_stats")

PREFIX = "admin:stats:page"
GOTO = "admin:stats:goto"
PAGE_SIZE = 20


def _format_table(users: list[dict], total: int, page_label: str) -> str:
    """Fixed-width table -- rendered inside <pre>, so columns must be padded."""
    usernames = [str(user.get("username", "unknown")) for user in users]
    telegram_ids = [str(user.get("telegramId") or user.get("telegram_id") or "-") for user in users]
    day_counts = [days_left(expire_at_of(user) or "") for user in users]

    name_w = max([8, *(len(v) for v in usernames)])
    tg_w = max([11, *(len(v) for v in telegram_ids)])
    days_w = max([4, *(len(v) for v in day_counts)])

    header = f"{'username':<{name_w}} | {'telegram_id':<{tg_w}} | {'days':>{days_w}}"
    lines = [
        "📊 Статистика:",
        f"Всего пользователей: {total}",
        f"Онлайн (из выборки): {sum(1 for user in users if is_online(user))}",
        "",
        page_label,
        header,
        "-" * len(header),
    ]
    lines.extend(
        f"{name:<{name_w}} | {tg_id:<{tg_w}} | {days:>{days_w}}"
        for name, tg_id, days in zip(usernames, telegram_ids, day_counts)
    )
    return "\n".join(lines)


async def render(target: Message, page: int, size: int, edit: bool) -> None:
    users, total = await fetch_users_page(page, size)
    text = _format_table(
        users,
        total,
        "Список пользователей (страница):" if edit else "Список пользователей (первые 50):",
    )
    body = f"<pre>{html.escape(text)}</pre>"
    keyboard = nav_keyboard(PREFIX, page, total, size, goto_callback_data=GOTO)
    if edit:
        await target.edit_text(body, reply_markup=keyboard)
    else:
        await target.answer(body, reply_markup=keyboard)


VIEW = register_view(PagedView(name="stats", size=PAGE_SIZE, render=render, count=count_users))


@router.callback_query(F.data == "admin:stats")
async def show_stats(callback: CallbackQuery):
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

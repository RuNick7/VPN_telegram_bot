"""Shared pieces of the admin user flows."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.db import UserRepository

from app.services.users import user_service

users_repo = UserRepository()

# Remnawave has no "never expires", so the UI's ♾️ option is a date far enough
# out that nobody will reach it; `days_left` renders it as ∞ rather than a
# five-figure day count.
DATE_FOREVER = datetime(2099, 1, 1, tzinfo=timezone.utc)


def parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def days_left(expire_at: str) -> str:
    """Whole days until expiry, `∞` for the forever date, `-` if unparseable."""
    parsed = parse_iso_datetime(expire_at) if expire_at else None
    if parsed is None:
        return "-"
    if parsed.year >= 2099:
        return "∞"
    return str((parsed.date() - datetime.now(timezone.utc).date()).days)


def telegram_id_of(user: dict[str, Any], fallback_username: str | None = None) -> int | None:
    """
    A panel user's Telegram ID.

    Falls back to the username, because accounts created by user_bot are named
    after the Telegram ID itself -- older ones predate the panel's telegramId
    field being populated.
    """
    raw = user.get("telegramId") or user.get("telegram_id")
    if raw:
        return int(raw)
    candidate = fallback_username or user.get("username")
    return int(candidate) if candidate and str(candidate).isdigit() else None


def expire_at_of(user: dict[str, Any]) -> str | None:
    return user.get("expireAt") or user.get("expire_at")


def is_online(user: dict[str, Any]) -> bool:
    return bool(user.get("onlineAt") or user.get("online_at"))


async def fetch_users_page(page: int, size: int) -> tuple[list[dict[str, Any]], int]:
    """One page of panel users as `(users, total)`."""
    data = await user_service.list_users(page=page, size=size)
    users = data.get("users") or []
    return users, data.get("total", len(users))


async def count_users() -> int:
    """Total panel users, fetching the smallest page that reports it."""
    _, total = await fetch_users_page(1, 1)
    return total


async def delete_user_everywhere(user_uuid: str | None, username: str, telegram_id: int | None) -> str:
    """
    Remove a user from the panel and from our database.

    Returns a human-readable summary of where the deletion actually landed --
    the two can legitimately disagree (a panel account with no subscription
    row, or a row whose panel account was already cleaned up).
    """
    deleted_in_panel = False
    if user_uuid:
        await user_service.delete_user(user_uuid)
        deleted_in_panel = True

    if telegram_id:
        deleted_in_db = await users_repo.delete_subscription_user(int(telegram_id))
    else:
        deleted_in_db = await users_repo.delete_subscription_user_by_username(username)

    places = [
        name
        for name, hit in (("Remnawave", deleted_in_panel), ("БД", deleted_in_db))
        if hit
    ]
    return " и ".join(places) if places else ""


# -- keyboards -------------------------------------------------------------


def skip_keyboard(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"admin:new_user:skip:{step}")]
        ]
    )


def _expire_presets(prefix: str, *, with_custom: bool) -> InlineKeyboardMarkup:
    """
    The expiry picker, shared by the create and edit flows.

    They differ only in the last row: creation offers "skip", editing offers
    "type a number of days".
    """
    last_row = (
        InlineKeyboardButton(text="✍️ Ввести дни", callback_data=f"{prefix}:custom")
        if with_custom
        else InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"{prefix}:skip")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="♾️ Навсегда", callback_data=f"{prefix}:forever"),
                InlineKeyboardButton(text="🗓️ Месяц", callback_data=f"{prefix}:month"),
            ],
            [InlineKeyboardButton(text="📅 Неделя", callback_data=f"{prefix}:week")],
            [last_row],
        ]
    )


def create_expire_keyboard() -> InlineKeyboardMarkup:
    return _expire_presets("admin:new_user:expire", with_custom=False)


def edit_expire_keyboard() -> InlineKeyboardMarkup:
    return _expire_presets("admin:edit_user:expire", with_custom=True)


def _search_mode_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """"Pick from a list" vs "type the username" -- the entry point for
    both the edit and delete flows."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Показать список", callback_data=f"{prefix}:list"),
                InlineKeyboardButton(text="✍️ Ввести username", callback_data=f"{prefix}:username"),
            ]
        ]
    )


def edit_start_keyboard() -> InlineKeyboardMarkup:
    return _search_mode_keyboard("admin:edit_user")


def delete_start_keyboard() -> InlineKeyboardMarkup:
    return _search_mode_keyboard("admin:del")


def edit_field_keyboard() -> InlineKeyboardMarkup:
    """
    Editable fields, panel-side first and database-side below.

    The split matters: the top group is pushed to Remnawave, the bottom group
    only exists in our own database (see `DB_ONLY_FIELDS` in `edit.py`).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Срок (expire)", callback_data="admin:edit_user:field:expire_at")],
            [
                InlineKeyboardButton(
                    text="Лимит (ГБ)", callback_data="admin:edit_user:field:traffic_limit_bytes"
                ),
                InlineKeyboardButton(text="Tag", callback_data="admin:edit_user:field:tag"),
            ],
            [
                InlineKeyboardButton(
                    text="HWID лимит", callback_data="admin:edit_user:field:hwid_device_limit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пригласивший", callback_data="admin:edit_user:field:referrer_tag"
                ),
                InlineKeyboardButton(
                    text="🔢 Приглашено", callback_data="admin:edit_user:field:referred_people"
                ),
            ],
        ]
    )


def edit_again_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Изменить ещё", callback_data="admin:edit_user:back")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "-"))

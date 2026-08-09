"""Shared pieces of the admin user flows."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.db import UserRepository
from tgvpn_shared.identity import looks_like_user_id
from tgvpn_shared.remnawave.client import panel_ref

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


# -- the account picker ----------------------------------------------------
#
# Sourced from our database, not from Remnawave. The panel holds profiles, not
# customers: an account created on the website is named `u-<uuid16>` there, and
# one whose profile never got created is absent altogether. Both were missing
# from the very screens meant to find people.


async def fetch_accounts_page(page: int, size: int) -> tuple[list[dict[str, Any]], int]:
    """One page of our own accounts as `(accounts, total)`."""
    total = await users_repo.count_accounts()
    rows = await users_repo.list_accounts_page(size, (max(1, page) - 1) * size)
    return rows, total


async def count_accounts() -> int:
    return await users_repo.count_accounts()


def account_label(row: dict[str, Any]) -> str:
    """
    How an account reads in a list of buttons.

    Whatever handle the person actually has, plus how long they have left --
    the two things an operator is looking for. The panel username is not one of
    them: `u-15e5a99848f04757` identifies nobody.
    """
    handle = (
        (f"@{row['telegram_tag']}" if row.get("telegram_tag") else None)
        or row.get("email")
        or (str(row["telegram_id"]) if row.get("telegram_id") else None)
        or str(row.get("id", "?"))[:8]
    )

    ends = int(row.get("subscription_ends") or 0)
    if ends <= 0:
        remaining = "нет подписки"
    else:
        days = (ends - int(datetime.now(timezone.utc).timestamp()) + 86399) // 86400
        remaining = f"{days} дн." if days > 0 else "истекла"

    return f"{handle} — {remaining}"


# -- finding a user by whatever the admin typed ----------------------------

# What every "type who you mean" prompt accepts. Written once because all
# three flows -- search, edit, delete -- ask the same question and used to
# accept three different answers.
HANDLE_PROMPT = (
    "Введите telegram_id, email, @ник, наш UUID или имя аккаунта в панели:"
)


async def find_db_row(needle: str) -> dict | None:
    """
    Find our own row for whatever the admin actually typed.

    A Telegram ID alone stopped being enough once people could sign up on the
    website: those accounts have none, so an admin searching for one was told
    the user does not exist. Email and our internal id are the handles they do
    have, and the panel username is what an operator sees in Remnawave and is
    the most likely thing to be copied out of it.
    """
    needle = needle.strip()
    if not needle:
        return None

    if needle.isdigit():
        row = await users_repo.get_user_by_id(int(needle))
        return dict(row) if row else None

    if "@" in needle:
        row = await users_repo.get_user_by_email(needle.lstrip("@"))
        if row:
            return dict(row)
        # Not an address after all -- try it as a @tag.
        row = await users_repo.get_user_by_tag(needle.lstrip("@"))
        return dict(row) if row else None

    # Our own id is only worth trying when the string could be one. Asking
    # anyway does not come back "not found" -- it raises, before the query is
    # even sent (see `looks_like_user_id`), and the panel-username attempt that
    # would have succeeded never happens. That is not hypothetical: a panel
    # username is the likeliest thing to be pasted here and never parses.
    lookups = (users_repo.get_user_by_uuid,) if looks_like_user_id(needle) else ()
    lookups += (users_repo.get_user_by_panel_username, users_repo.get_user_by_tag)

    for lookup in lookups:
        row = await lookup(needle)
        if row:
            return dict(row)
    return None


def panel_names_for(needle: str, row: dict | None) -> list[str]:
    """
    Names to try in the panel, most authoritative first.

    The stored panel username is what we recorded when the account was made.
    `str(telegram_id)` is what accounts created before the identity rework are
    called. Whatever was typed is the fallback, and is right when the admin
    copied a username straight out of Remnawave.
    """
    candidates = [needle]
    if row:
        telegram_id = row.get("telegram_id")
        candidates = [
            name
            for name in (
                row.get("remnawave_username"),
                str(telegram_id) if telegram_id else None,
                needle,
            )
            if name
        ]
    # Preserve order, drop repeats.
    return list(dict.fromkeys(candidates))


async def find_panel_user(needle: str, row: dict | None) -> tuple[dict | None, str | None]:
    """
    The panel account for this person, and the name it answered to.

    Returns `(None, None)` rather than raising when the panel has nothing:
    an account can legitimately exist on our side only, and every caller has
    something useful to say about that.
    """
    for name in panel_names_for(needle, row):
        found = await user_service.get_user_by_username(name)
        if found and panel_ref(found):
            return found, name
    return None, None


async def delete_user_everywhere(
    user_uuid: str | None,
    username: str,
    telegram_id: int | None,
    row_id: str | None = None,
) -> str:
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

    if row_id:
        # By our own id when we have it. The fallbacks below match on
        # telegram_tag or telegram_id, and a website account has neither -- so
        # its row survived a deletion that reported success.
        deleted_in_db = await users_repo.delete_user_row(row_id)
    elif telegram_id:
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
    """
    "Pick from a list" vs "type who you mean" -- the entry point for both the
    edit and delete flows.

    The second button no longer says "username": these prompts take a Telegram
    ID, an email, a @tag, our UUID or the panel name, and naming only the one
    handle an admin is least likely to have was hiding the other four.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Показать список", callback_data=f"{prefix}:list"),
                InlineKeyboardButton(text="✍️ Найти по ID / почте", callback_data=f"{prefix}:username"),
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
                ),
                # The one field here that decides whether the account can be
                # signed into at all. "Я опечатался при регистрации" had no
                # answer before this button.
                InlineKeyboardButton(text="✉️ Почта", callback_data="admin:edit_user:field:email"),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пригласивший", callback_data="admin:edit_user:field:referrer_tag"
                ),
                InlineKeyboardButton(
                    text="🔢 Приглашено", callback_data="admin:edit_user:field:referred_people"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📶 Бесплатно ГБ/мес", callback_data="admin:edit_user:field:lte_free_gb"
                ),
                InlineKeyboardButton(
                    text="💾 Баланс трафика", callback_data="admin:edit_user:field:lte_balance_gb"
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

"""Look one user up across both the panel and our database."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.admin.users.common import (
    days_left,
    escape,
    expire_at_of,
    is_online,
    users_repo,
)
from app.services.users import user_service
from app.states.admin import UserSearchState

router = Router(name="admin_users_search")


def _fmt_ts_utc(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def build_report(needle: str, panel_user: dict | None, db_rows: list[dict]) -> str:
    """
    Side-by-side view of what each system knows about one Telegram ID.

    Showing both is the point: the two drifting apart (a panel account with no
    subscription row, or the reverse) is exactly what an admin runs this
    search to diagnose.
    """
    lines = [f"🔎 Поиск пользователя: <code>{escape(needle)}</code>", "", "<b>Remnawave</b>"]

    if panel_user:
        expire_at = expire_at_of(panel_user) or "-"
        traffic = panel_user.get("trafficLimitBytes") or panel_user.get("traffic_limit_bytes")
        lines.extend(
            [
                f"username: <code>{escape(panel_user.get('username'))}</code>",
                f"uuid: <code>{escape(panel_user.get('uuid'))}</code>",
                f"tag: <code>{escape(panel_user.get('tag'))}</code>",
                f"online: {'да' if is_online(panel_user) else 'нет'}",
                f"expire_at: <code>{escape(expire_at)}</code>",
                f"days_left: <code>{escape(days_left(expire_at) if isinstance(expire_at, str) else '-')}</code>",
                f"traffic_limit_bytes: <code>{escape(traffic)}</code>",
            ]
        )
    else:
        lines.append("не найден")

    lines.extend(["", f"<b>База данных</b> (записей: {len(db_rows)})"])
    if not db_rows:
        lines.append("не найден")
    for row in db_rows:
        lines.extend(
            [
                f"• id=<code>{escape(row.get('id'))}</code>"
                f" ends=<code>{_fmt_ts_utc(row.get('subscription_ends'))}</code>"
                f" reminded=<code>{escape(row.get('reminded'))}</code>"
                f" stage=<code>{escape(row.get('nurture_stage'))}</code>",
                f"  tg=<code>{escape(row.get('telegram_id') or '-')}</code>"
                f" tag=<code>{escape(row.get('telegram_tag') or '-')}</code>"
                f" email=<code>{escape(row.get('email') or '-')}</code>",
                f"  referred=<code>{row.get('referred_people', 0)}</code>"
                f" gifted=<code>{row.get('gifted_subscriptions', 0)}</code>"
                f" tier=<code>{escape(row.get('squad_tier') or '-')}</code>"
                f" panel=<code>{escape(row.get('remnawave_username') or '-')}</code>",
            ]
        )

    return "\n".join(lines)


async def find_db_rows(needle: str) -> list[dict]:
    """
    Find a user by whatever the admin actually typed.

    Telegram ID alone stopped being enough once people could sign up on the
    website: those accounts have no Telegram ID at all, so an admin searching
    for one would be told the user does not exist. Email and our internal id
    are the handles they do have; the panel username is what an operator sees
    in Remnawave and is the most likely thing to be copied from there.
    """
    if needle.isdigit():
        row = await users_repo.get_user_by_id(int(needle))
        return [dict(row)] if row else []

    if "@" in needle:
        row = await users_repo.get_user_by_email(needle.lstrip("@"))
        if row:
            return [dict(row)]
        # Not an address after all -- try it as a @tag.
        row = await users_repo.get_user_by_tag(needle.lstrip("@"))
        return [dict(row)] if row else []

    row = await users_repo.get_user_by_uuid(needle)
    if row:
        return [dict(row)]
    row = await users_repo.get_user_by_panel_username(needle)
    if row:
        return [dict(row)]
    row = await users_repo.get_user_by_tag(needle)
    return [dict(row)] if row else []


@router.callback_query(F.data == "admin:user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSearchState.telegram_id)
    await callback.message.answer(
        "Введите telegram_id, email, @ник, наш UUID или имя аккаунта в панели:"
    )
    await callback.answer()


@router.message(UserSearchState.telegram_id)
async def handle_search_input(message: Message, state: FSMContext):
    needle = (message.text or "").strip()
    if not needle:
        await message.answer("❌ Введите telegram_id, email, @ник или UUID.")
        return

    try:
        db_rows = await find_db_rows(needle)
    except Exception as exc:
        await message.answer(f"⚠️ Ошибка чтения базы данных: {exc}")
        await state.clear()
        return

    # Ask the panel by the name it would actually know this user under: their
    # recorded panel username first, then whatever was typed.
    panel_names = [needle]
    if db_rows:
        stored = db_rows[0].get("remnawave_username")
        telegram_id = db_rows[0].get("telegram_id")
        panel_names = [n for n in (stored, str(telegram_id) if telegram_id else None, needle) if n]

    panel_user: dict | None = None
    for name in panel_names:
        try:
            found = await user_service.get_user_by_username(name)
        except Exception as exc:
            # Report and keep going -- the database half of the report is
            # still useful when the panel is unreachable.
            await message.answer(f"⚠️ Ошибка запроса к Remnawave: {exc}")
            break
        if found:
            panel_user = found
            break

    await message.answer(build_report(needle, panel_user, db_rows), parse_mode="HTML")
    await state.clear()

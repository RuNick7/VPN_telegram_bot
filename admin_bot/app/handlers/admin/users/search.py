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


def build_report(telegram_id: int, panel_user: dict | None, db_rows: list[dict]) -> str:
    """
    Side-by-side view of what each system knows about one Telegram ID.

    Showing both is the point: the two drifting apart (a panel account with no
    subscription row, or the reverse) is exactly what an admin runs this
    search to diagnose.
    """
    lines = [f"🔎 Поиск пользователя: <code>{telegram_id}</code>", "", "<b>Remnawave</b>"]

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
                f"  tag=<code>{escape(row.get('telegram_tag') or '-')}</code>"
                f" referred=<code>{row.get('referred_people', 0)}</code>"
                f" gifted=<code>{row.get('gifted_subscriptions', 0)}</code>",
            ]
        )

    return "\n".join(lines)


@router.callback_query(F.data == "admin:user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSearchState.telegram_id)
    await callback.message.answer("Введите telegram_id (он же username) для поиска:")
    await callback.answer()


@router.message(UserSearchState.telegram_id)
async def handle_search_input(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Введите telegram_id числом.")
        return

    telegram_id = int(raw)
    panel_user: dict | None = None
    try:
        found = await user_service.get_user_by_username(raw)
        panel_user = found or None
    except Exception as exc:
        # Report and keep going -- the database half of the report is still
        # useful when the panel is unreachable.
        await message.answer(f"⚠️ Ошибка запроса к Remnawave: {exc}")

    try:
        db_rows = await users_repo.get_subscription_rows_by_telegram_id(telegram_id)
    except Exception as exc:
        await message.answer(f"⚠️ Ошибка чтения базы данных: {exc}")
        await state.clear()
        return

    await message.answer(build_report(telegram_id, panel_user, db_rows), parse_mode="HTML")
    await state.clear()

"""Look one user up across both the panel and our database."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from tgvpn_shared.lte_quota import format_traffic, remaining_now

from app.config.settings import settings
from app.handlers.admin.users.common import (
    HANDLE_PROMPT,
    days_left,
    escape,
    expire_at_of,
    find_db_row,
    find_panel_user,
    is_online,
)
from app.states.admin import UserSearchState

router = Router(name="admin_users_search")


def _fmt_ts_utc(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def _days_from_epoch(subscription_ends: int | None) -> str:
    """Whole days left on the subscription we recorded, `-` if there is none."""
    if not subscription_ends:
        return "-"
    remaining = int(subscription_ends) - int(datetime.now(tz=timezone.utc).timestamp())
    return str(max(0, remaining // 86400)) if remaining > 0 else "истекла"


def _traffic_line(
    row: dict, *, free_gb_per_cycle: int, cycle_seconds: int, now: int | None = None
) -> str | None:
    """
    Spent and remaining on the metered squad, or None if there is nothing to
    say -- an account `lte_cycle_start` has never touched has no reading to
    show, and showing a fabricated zero for it would read as "spent nothing"
    rather than "was never metered", which is a different fact.

    "Spent" is the raw `lte_last_usage_bytes` the last monitor pass measured,
    not a total minus `remaining_now` -- an admin chasing a "why was I
    blocked" ticket needs the number the monitor actually saw, not one
    reconstructed from it.
    """
    if not row.get("lte_cycle_start"):
        return None
    now = int(now if now is not None else time.time())
    spent = max(0, int(row.get("lte_last_usage_bytes") or 0))
    remaining = remaining_now(
        state=row, global_free_gb=free_gb_per_cycle, cycle_seconds=cycle_seconds, now=now
    )
    blocked = " (заблокирован)" if row.get("lte_blocked") else ""
    return (
        f"Трафик белых списков: потрачено <b>{escape(format_traffic(spent))}</b>, "
        f"осталось <b>{escape(format_traffic(remaining))}</b>{blocked}"
    )


def build_summary(
    row: dict,
    *,
    lte_free_gb_per_cycle: int = 10,
    lte_cycle_seconds: int = 30 * 86400,
) -> list[str]:
    """
    The things an admin actually opened this search to see.

    Everything below in the report is a comparison between two systems, which
    is what you read when something is wrong. This is what you read when
    nothing is: who this is, how to reach them, how long they have left, and
    -- when the metered squad has ever touched them -- what their traffic
    looks like.
    """
    ends = row.get("subscription_ends")
    lines = [
        "<b>Кратко</b>",
        f"Telegram ID: <code>{escape(row.get('telegram_id') or '—')}</code>",
        f"Ник: <code>{'@' + str(row['telegram_tag']) if row.get('telegram_tag') else '—'}</code>",
        f"Почта: <code>{escape(row.get('email') or '—')}</code>",
        f"Осталось дней: <b>{escape(_days_from_epoch(ends))}</b>"
        + (f" (до {_fmt_ts_utc(ends)})" if ends else ""),
    ]
    traffic = _traffic_line(
        row, free_gb_per_cycle=lte_free_gb_per_cycle, cycle_seconds=lte_cycle_seconds
    )
    if traffic:
        lines.append(traffic)
    return lines


def build_report(needle: str, panel_user: dict | None, db_rows: list[dict]) -> str:
    """
    Side-by-side view of what each system knows about one account.

    Showing both is the point: the two drifting apart (a panel account with no
    subscription row, or the reverse) is exactly what an admin runs this
    search to diagnose. The summary above it is for the other nine times out of
    ten, when nothing has drifted and the question is simply who this is.
    """
    lines = [f"🔎 Поиск пользователя: <code>{escape(needle)}</code>", ""]

    if db_rows:
        lines.extend(
            build_summary(
                db_rows[0],
                lte_free_gb_per_cycle=settings.lte_free_gb_per_cycle,
                lte_cycle_seconds=settings.lte_cycle_seconds,
            )
        )
        lines.append("")

    lines.append("<b>Remnawave</b>")

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


@router.callback_query(F.data == "admin:user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSearchState.telegram_id)
    await callback.message.answer(HANDLE_PROMPT)
    await callback.answer()


@router.message(UserSearchState.telegram_id)
async def handle_search_input(message: Message, state: FSMContext):
    needle = (message.text or "").strip()
    if not needle:
        await message.answer("❌ Введите telegram_id, email, @ник или UUID.")
        return

    try:
        row = await find_db_row(needle)
    except Exception as exc:
        await message.answer(f"⚠️ Ошибка чтения базы данных: {exc}")
        await state.clear()
        return

    panel_user: dict | None = None
    try:
        panel_user, _ = await find_panel_user(needle, row)
    except Exception as exc:
        # Report and keep going -- the database half of the report is still
        # useful when the panel is unreachable.
        await message.answer(f"⚠️ Ошибка запроса к Remnawave: {exc}")

    await message.answer(
        build_report(needle, panel_user, [row] if row else []), parse_mode="HTML"
    )
    await state.clear()

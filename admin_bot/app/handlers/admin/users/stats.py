"""
Aggregate statistics screen.

This used to be a paginated table of every panel user -- 25 pages of
username/telegram_id/days that answered no question an admin actually had, and
whose prev/next buttons broke as soon as Telegram rejected an unchanged
`edit_text`. It is now one message of totals, computed in two SQL aggregates
plus one panel call.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.handlers.admin.users.common import users_repo
from app.services.users import user_service

router = Router(name="admin_users_stats")

# A subscription ending inside this window is "expiring soon" -- the number an
# admin looks at to judge how much renewal revenue is in flight.
EXPIRING_SOON_DAYS = 3


def _refresh_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:stats:refresh")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _percent(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "0%"


async def _panel_numbers() -> tuple[int | None, int | None]:
    """
    `(total_users, online_now)` from the panel, or `(None, None)` if it's down.

    The panel is a separate system from our database and can be unreachable
    independently, so its numbers are optional -- the database half of the
    report is still worth showing without them.
    """
    try:
        data = await user_service.list_users(page=1, size=1)
        panel_total = data.get("total")
    except Exception:
        return None, None

    try:
        system = await user_service.client.get_system_stats()
        online = (system.get("users") or {}).get("onlineNow")
        if online is None:
            online = (system.get("nodes") or {}).get("totalOnline")
    except Exception:
        online = None
    return panel_total, online


def build_report(
    db: dict,
    payments: dict,
    panel_total: int | None,
    online_now: int | None,
) -> str:
    total = int(db.get("total") or 0)
    active = int(db.get("active") or 0)
    expired = int(db.get("expired") or 0)

    lines = [
        "📊 <b>Статистика</b>",
        "",
        "<b>Подписки</b>",
        f"• Всего пользователей: <b>{total}</b>",
        f"• Активных: <b>{active}</b> ({_percent(active, total)})",
        f"• Истёкших: <b>{expired}</b> ({_percent(expired, total)})",
        f"• Истекают в ближайшие {EXPIRING_SOON_DAYS} дн.: <b>{db.get('expiring_soon', 0)}</b>",
        "",
        "<b>Приток</b>",
        f"• За сутки: <b>{db.get('new_today', 0)}</b>",
        f"• За неделю: <b>{db.get('new_week', 0)}</b>",
        f"• За месяц: <b>{db.get('new_month', 0)}</b>",
        "",
        "<b>Рефералы и подарки</b>",
        f"• Указали пригласившего: <b>{db.get('with_referrer', 0)}</b>",
        f"• Бонусов начислено: <b>{db.get('referrals_awarded', 0)}</b>",
        f"• Всего приглашено: <b>{db.get('referred_people', 0)}</b>",
        f"• Подарочных подписок: <b>{db.get('gifted_subscriptions', 0)}</b>",
        "",
        "<b>Платежи</b>",
        f"• Успешных: <b>{payments.get('succeeded', 0)}</b>"
        f" (за 30 дн.: {payments.get('succeeded_month', 0)})",
        f"• В обработке: <b>{payments.get('processing', 0)}</b>",
        f"• С ошибкой: <b>{payments.get('failed', 0)}</b>",
        "",
        "<b>Панель Remnawave</b>",
    ]

    if panel_total is None:
        lines.append("• ⚠️ Панель недоступна")
    else:
        lines.append(f"• Пользователей в панели: <b>{panel_total}</b>")
        if online_now is not None:
            lines.append(f"• Онлайн сейчас: <b>{online_now}</b>")
        # A gap between the two systems is the thing worth surfacing: it means
        # accounts exist on one side and not the other.
        if panel_total != total:
            lines.append(f"• ⚠️ Расхождение с БД: <b>{panel_total - total:+d}</b>")

    lines.extend(["", f"✉️ С указанным email: {db.get('with_email', 0)}"])
    return "\n".join(lines)


async def render(callback: CallbackQuery, *, edit: bool) -> None:
    db = await users_repo.get_stats(EXPIRING_SOON_DAYS)
    payments = await users_repo.get_payment_stats()
    panel_total, online_now = await _panel_numbers()
    text = build_report(db, payments, panel_total, online_now)

    if edit:
        await callback.message.edit_text(text, reply_markup=_refresh_keyboard())
    else:
        await callback.message.answer(text, reply_markup=_refresh_keyboard())


@router.callback_query(F.data == "admin:stats")
async def show_stats(callback: CallbackQuery):
    try:
        await render(callback, edit=False)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data == "admin:stats:refresh")
async def refresh_stats(callback: CallbackQuery):
    try:
        await render(callback, edit=True)
        await callback.answer("Обновлено")
    except Exception as exc:
        # Telegram rejects an edit that would leave the message unchanged --
        # for a refresh button that just means nothing moved since last time.
        if "message is not modified" in str(exc).lower():
            await callback.answer("Без изменений")
            return
        await callback.message.answer(f"❌ Ошибка: {exc}")
        await callback.answer()

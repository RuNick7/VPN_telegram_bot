"""
Payments that need a human.

A payment stuck out of `succeeded` means somebody paid and was not credited.
Nothing surfaced that: the row was an id and a status, so finding out who had
paid meant reading the YooKassa dashboard and matching timestamps by hand --
which is how one sat unnoticed for a day.

Nothing here changes a payment. Deciding that one succeeded requires
re-fetching it from YooKassa server-to-server, because the callback carries no
signature of its own; that lives in the webhook and only there. This screen
reads, and tells the operator which two levers exist.
"""

from __future__ import annotations

import html
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.db import PaymentRepository

router = Router(name="admin_payments")

_payments = PaymentRepository()

LIMIT = 15

# A pending payment younger than this is somebody still on the payment page,
# not a problem. Anything older has been abandoned or has failed quietly.
PENDING_GRACE_SECONDS = 15 * 60

PURPOSE_LABELS = {
    "subscription": "подписка",
    "gift": "подарок",
    "traffic": "трафик",
}


def _escape(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _age(updated_at: int | None, now: int) -> str:
    if not updated_at:
        return "—"
    minutes = max(0, (now - int(updated_at)) // 60)
    if minutes < 60:
        return f"{minutes} мин назад"
    if minutes < 60 * 24:
        return f"{minutes // 60} ч назад"
    return f"{minutes // (60 * 24)} дн назад"


def _who(row) -> str:
    if row["telegram_tag"]:
        return f"@{row['telegram_tag']}"
    if row["email"]:
        return str(row["email"])
    if row["telegram_id"]:
        return str(row["telegram_id"])
    return "не определён"


def needs_attention(row, now: int) -> bool:
    """
    Whether this row is a problem rather than a payment in flight.

    A fresh `pending` is the customer still deciding. Everything else -- an
    error, a stuck claim, an old abandoned pending -- is worth a look.
    """
    if row["status"] != "pending":
        return True
    return (now - int(row["updated_at"] or 0)) > PENDING_GRACE_SECONDS


def build_report(rows: list, now: int) -> str:
    interesting = [row for row in rows if needs_attention(row, now)]
    lines = ["💳 <b>Платежи, требующие внимания</b>", ""]
    if not interesting:
        lines.append("Ничего. Все платежи завершены или ещё в процессе оплаты.")
        return "\n".join(lines)

    for row in interesting:
        purpose = PURPOSE_LABELS.get(row["purpose"], row["purpose"] or "—")
        lines.append(
            f"• <code>{_escape(row['payment_id'])}</code>\n"
            f"    {_escape(row['status'])} · {purpose}"
            + (f" · {row['days']} дн." if row["days"] else "")
            + f" · {_age(row['updated_at'], now)}\n"
            f"    кто: {_escape(_who(row))}"
        )

    lines.extend(
        [
            "",
            "Что можно сделать:",
            "• переотправить вебхук из кабинета ЮKassa — платёж начислится сам;",
            "• либо начислить дни вручную через «Редактировать пользователя» → «Срок».",
        ]
    )
    return "\n".join(lines)


@router.callback_query(F.data == "admin:payments")
async def show_payments(callback: CallbackQuery):
    try:
        rows = await _payments.unsettled(LIMIT)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка чтения базы: {exc}")
        await callback.answer()
        return

    await callback.message.answer(
        build_report(list(rows), int(time.time())),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]]
        ),
    )
    await callback.answer()

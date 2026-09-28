"""
Gifts: who bought them, whether they have been used, and issuing one by hand.

Neither was visible anywhere. A gift bought on the site is delivered by a
Telegram message the buyer may not be able to receive, and when that went
wrong -- or when a payment failed and somebody had to be compensated -- the
only tool was the generic promo-code form, which produces a code with no
buyer, no record of why, and no way to tell it apart afterwards.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from tgvpn_shared.db import PromoRepository, generate_gift_code
from tgvpn_shared.settings import get_settings

from app.states.admin import GiftIssueState

router = Router(name="admin_gifts")

_promo = PromoRepository()

# How many to show. A chat message has a length limit and an operator scanning
# a list is not reading a hundred of them.
RECENT_LIMIT = 15


def _escape(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _date(ts) -> str:
    if not ts:
        return "—"
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).strftime("%d.%m.%Y")
    return str(ts)


def _who(tag, email, telegram_id) -> str:
    """Name somebody by whichever handle they have."""
    if tag:
        return f"@{tag}"
    if email:
        return str(email)
    if telegram_id:
        return str(telegram_id)
    return "—"


def build_gift_report(rows: list, stats: dict) -> str:
    lines = [
        "🎁 <b>Подарки</b>",
        f"Всего: <b>{stats.get('total', 0)}</b>"
        f" · активировано: <b>{stats.get('redeemed', 0)}</b>"
        f" · за 30 дней: <b>{stats.get('last_month', 0)}</b>",
        "",
    ]
    if not rows:
        lines.append("Пока ни одного.")
        return "\n".join(lines)

    for row in rows:
        redeemed = row["redeemed_at"]
        mark = "✅" if redeemed else "⏳"
        buyer = _who(row["buyer_tag"], row["buyer_email"], row["buyer_telegram_id"])
        line = (
            f"{mark} <code>{_escape(row['code'])}</code> · {row['days']} дн."
            f" · {_date(row['created_at'])}\n"
            f"    купил: {_escape(buyer)}"
        )
        if redeemed:
            taker = _who(row["taker_tag"], row["taker_email"], None)
            line += f" → активировал: {_escape(taker)} ({_date(redeemed)})"
        lines.append(line)

    return "\n".join(lines)


@router.callback_query(F.data == "admin:gifts")
async def show_gifts(callback: CallbackQuery):
    try:
        rows = await _promo.recent_gifts(RECENT_LIMIT)
        stats = await _promo.gift_stats()
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка чтения базы: {exc}")
        await callback.answer()
        return

    await callback.message.answer(
        build_gift_report(list(rows), stats),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Выдать подарок", callback_data="admin:gift_issue")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:gift_issue")
async def start_issue(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GiftIssueState.days)
    await callback.message.answer(
        "На сколько дней выдать подарок? Введите число (например 30).\n\n"
        "Код будет одноразовым и без покупателя — его можно отдать кому угодно."
    )
    await callback.answer()


@router.message(GiftIssueState.days)
async def issue_gift(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not 1 <= int(text) <= 3650:
        await message.answer("❌ Введите число дней от 1 до 3650.")
        return

    days = int(text)
    code = generate_gift_code()
    try:
        # No creator of either kind: nobody paid for this one, so nobody is
        # barred from redeeming it and support can hand it to whoever the
        # compensation is for.
        await _promo.create_gift_promo(code, days, creator_id=None, creator_user_id=None)
    except Exception as exc:
        await message.answer(f"❌ Не удалось создать подарок: {exc}")
        await state.clear()
        return

    link = get_settings().gift_link(code)
    reply = (
        f"✅ Подарок на <b>{days} дн.</b> создан.\n\n"
        f"Код: <code>{html.escape(code)}</code>"
    )
    if link:
        reply += f"\nСсылка: {html.escape(link)}"
    reply += "\n\nАктивировать можно один раз — кодом в боте или по ссылке на сайте."

    await message.answer(reply, parse_mode="HTML")
    await state.clear()

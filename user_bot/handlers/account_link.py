"""
Attaching a Telegram account to a website account.

The website mints a one-time token and hands the user a
`t.me/<bot>?start=link_<token>` link. Opening it puts the token in `/start`'s
payload, and this is the other end of that handshake: it proves the person
driving the browser session and the person in this chat are the same, without
either side typing an identifier at the other.

Two outcomes. If this Telegram user has no account, the website account simply
gains a Telegram identity -- nothing is merged and nothing can be lost. If
they already have one, the two are folded together, and the rule that matters
is that **days add up**: someone who bought a month on the site and has two
weeks left in the bot ends up with six weeks.
"""

import logging
import time

from aiogram import F, Router, types
from aiogram.filters import CommandObject, CommandStart
from tgvpn_shared.db import AccountLinkRepository, UserRepository
from tgvpn_shared.identity import choose_survivor, days_from, plan_merge

from handlers.keyboards import back_to_menu_keyboard

router = Router()
logger = logging.getLogger(__name__)

_users = UserRepository()
_links = AccountLinkRepository()

# The `/start` payload prefix the website builds its links with.
LINK_PREFIX = "link_"


def extract_link_token(payload: str | None) -> str | None:
    """The token out of a `/start link_<token>` payload, or None."""
    if not payload:
        return None
    payload = payload.strip()
    if not payload.startswith(LINK_PREFIX):
        return None
    token = payload[len(LINK_PREFIX):]
    return token or None


async def _expire_leftover_panel_account(uuid: str) -> None:
    """
    Retire the panel account of an absorbed row.

    Its days were just added to the survivor, so leaving it live would hand
    the user the same period twice on two different connection links. Expiring
    rather than deleting: an operator can still see what happened, and a
    deletion we got wrong could not be undone.
    """
    from app.services.remnawave.vpn_service import get_client
    from tgvpn_shared.free_tier import format_panel_timestamp

    try:
        await get_client().update_user(
            {"uuid": uuid, "expireAt": format_panel_timestamp(int(time.time()))}
        )
        logger.info("[LINK] Leftover panel account %s expired", uuid)
    except Exception as exc:
        # Loud, because the user now has a link that outlives what they paid
        # for, and only an operator can clean that up.
        logger.error("[LINK] Could not expire leftover panel account %s: %s", uuid, exc)


async def link_account(token: str, telegram_id: int, telegram_tag: str) -> str:
    """
    Redeem a link token for this Telegram user. Returns a message for them.

    Returns rather than sends so the decision is testable without a bot.
    """
    web_user_id = await _links.consume(token)
    if web_user_id is None:
        return (
            "❌ <b>Ссылка недействительна</b>\n\n"
            "Она истекла или уже была использована. "
            "Запросите новую в личном кабинете на сайте."
        )

    web_row = await _users.get_user_by_uuid(web_user_id)
    if web_row is None:
        logger.error("[LINK] Token resolved to a missing user %s", web_user_id)
        return "❌ Аккаунт с сайта не найден. Напишите в поддержку."
    web_account = dict(web_row)

    existing_row = await _users.get_user_by_id(telegram_id)

    # Already the same account -- the user pressed the link twice, or linked
    # from a browser already signed in as this Telegram account.
    if existing_row is not None and str(existing_row["id"]) == str(web_account["id"]):
        return "✅ <b>Аккаунт уже привязан</b>\n\nВсё в порядке, ничего делать не нужно."

    if existing_row is None:
        # Nothing to merge: the website account simply gains a Telegram
        # identity. Nothing can be lost on this path.
        if not await _users.attach_telegram(str(web_account["id"]), telegram_id, telegram_tag):
            logger.error("[LINK] Account %s already had a telegram_id", web_account["id"])
            return "❌ Этот аккаунт уже привязан к другому Telegram. Напишите в поддержку."
        logger.info("[LINK] Web account %s attached to telegram %s", web_account["id"], telegram_id)
        return (
            "✅ <b>Telegram привязан</b>\n\n"
            "Теперь подписка, трафик и оплата работают и в боте, и на сайте.\n\n"
            "Откройте /start."
        )

    # Both sides exist: fold them into one.
    now = int(time.time())
    survivor, absorbed = choose_survivor(dict(existing_row), web_account)
    plan = plan_merge(survivor=survivor, absorbed=absorbed, now=now)

    await _users.apply_merge(plan)
    if plan.expire_panel_uuid:
        await _expire_leftover_panel_account(plan.expire_panel_uuid)

    logger.info(
        "[LINK] Merged %s into %s; expiry now %s",
        plan.absorbed_id, plan.survivor_id, plan.subscription_ends,
    )
    return (
        "✅ <b>Аккаунты объединены</b>\n\n"
        f"Дни подписки сложены: осталось <b>{days_from(plan.subscription_ends, now)} дн.</b>\n"
        "Купленный трафик и приглашённые тоже перенесены.\n\n"
        "Откройте /start."
    )


@router.message(CommandStart(deep_link=True), F.text.contains(LINK_PREFIX))
async def start_with_link_token(message: types.Message, command: CommandObject) -> None:
    """
    Handle `/start link_<token>`.

    Registered on its own router ahead of the plain `/start` handler, and
    filtered narrowly enough that any other deep link falls through to it.
    """
    token = extract_link_token(command.args)
    if token is None:
        return

    try:
        text = await link_account(
            token, message.from_user.id, message.from_user.username or ""
        )
    except Exception as exc:
        logger.exception("[LINK] Failed to link account: %s", exc)
        text = "❌ Не удалось привязать аккаунт. Попробуйте позже или напишите в поддержку."

    await message.answer(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

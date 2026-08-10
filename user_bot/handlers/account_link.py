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

from handlers.constants import trial_days, trial_link_bonus_days
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


async def _survivor_has_panel_account(survivor: dict) -> bool | None:
    """
    Whether the surviving account already has a panel profile -- looked up,
    not read off `remnawave_uuid`.

    That column is empty for every account created before the identity rework
    until something resolves it, and those accounts are named
    `str(telegram_id)` in the panel. Believing the column here is what made a
    merge hand the survivor the *other* account's profile while its own kept
    running; see `plan_merge`.

    `resolve_panel_user` is the same lookup the rest of the bot uses, so a hit
    also backfills the row -- one legacy account retired per merge. The dict is
    updated too, because `plan_merge` reads it a few lines later.

    Returns None when the panel could not be asked, which is not the same as
    "no" and is not treated as one.
    """
    from app.services.remnawave.vpn_service import resolve_panel_user
    from tgvpn_shared.remnawave.client import panel_ref

    try:
        profile = await resolve_panel_user(survivor)
    except Exception as exc:
        # Not fatal. The merge still happens; it just declines to adopt, which
        # is the recoverable side of the choice.
        logger.warning("[LINK] Could not resolve the survivor's panel account: %s", exc)
        return None

    if profile is None:
        return False
    if ref := panel_ref(profile):
        survivor["remnawave_uuid"] = ref
        survivor["remnawave_username"] = profile.get("username")
    return True


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

        # This, and only this, is the path the bonus is paid on. The Telegram
        # account is new -- it had no row of its own, so it has never collected
        # a signup trial and nothing has been summed. Where both sides already
        # existed the merge below adds their days together instead, which is
        # why paying here as well would put 21 free days within reach of anyone
        # who registered twice deliberately.
        bonus = trial_link_bonus_days()
        granted = await _users.grant_link_bonus(str(web_account["id"]), bonus) if bonus else None

        text = (
            "✅ <b>Telegram привязан</b>\n\n"
            "Теперь подписка, трафик и оплата работают и в боте, и на сайте.\n\n"
        )
        if granted is not None:
            text += (
                f"🎁 Начислено <b>{bonus} дн.</b> за привязку — "
                f"осталось <b>{days_from(granted, int(time.time()))} дн.</b>\n\n"
            )
        return text + "Откройте /start."

    # Both sides exist: fold them into one.
    now = int(time.time())
    survivor, absorbed = choose_survivor(dict(existing_row), web_account)
    # The trial length is passed in so the merge can refuse to hand the same
    # person a second free period; the panel answer so it does not mistake an
    # unfilled column for an account that isn't there. Both are things
    # `plan_merge` cannot work out on its own.
    plan = plan_merge(
        survivor=survivor,
        absorbed=absorbed,
        now=now,
        trial_days=trial_days(),
        survivor_has_panel_account=await _survivor_has_panel_account(survivor),
    )

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

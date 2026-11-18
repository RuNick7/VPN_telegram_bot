import asyncio
from html import escape

from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from tgvpn_shared.db import PromoRepository, UserRepository
from aiogram.exceptions import TelegramBadRequest

from handlers.keyboards import (
    REFERRAL_CALLBACK,
    REFERRAL_INVITES_CALLBACK,
    back_to_menu_keyboard,
    referral_invites_keyboard,
    referral_keyboard,
)
from handlers.constants import SECONDS_IN_DAY, trial_days
from handlers.utils import escape_markdown_v2, get_subscription_price


router = Router()
_users = UserRepository()
_promo = PromoRepository()

# Ceiling on a full extend round-trip (several panel calls), so a slow
# Remnawave can't leave the user staring at a dead button.
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0


async def _extend_subscription_async(telegram_id: int, added_days: int) -> str:
    """Extend with a hard timeout, reported to the user rather than raised."""
    from app.services.remnawave import vpn_service as vpn

    try:
        return await asyncio.wait_for(
            vpn.extend_subscription(telegram_id, added_days),
            timeout=REMNAWAVE_EXTEND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return f"❌ Таймаут продления подписки (>{REMNAWAVE_EXTEND_TIMEOUT_SECONDS}s)"


class ReferralFSM(StatesGroup):
    waiting_for_tag = State()


class PromoState(StatesGroup):
    waiting_for_promo = State()


def _has_paid_before(user_row) -> bool:
    """Best-effort check: user extended beyond initial trial period."""
    if not user_row:
        return False
    try:
        created_at = int(user_row["created_at"] or 0)
        subscription_ends = int(user_row["subscription_ends"] or 0)
    except (TypeError, ValueError, IndexError, KeyError):
        return False
    if created_at <= 0 or subscription_ends <= 0:
        return False
    trial_end = created_at + trial_days() * SECONDS_IN_DAY
    return subscription_ends > trial_end


# -- «🎁 Реферальная программа» and «👥 Мои приглашения» -----------------------
#
# HTML rather than MarkdownV2: the screens carry Telegram tags, prices and
# dashes, and MarkdownV2 refuses the whole message over one unescaped
# character -- which is how the old referrer screen ended up never showing.

# Above five friends the price stops falling (`get_subscription_price` caps
# the tier), so the table ends at «5 и больше».
MAX_REFERRAL_TIER = 5
_TIER_LABELS = ["0 друзей", "1 друг", "2 друга", "3 друга", "4 друга", "5 и больше"]

# How many invitees «Мои приглашения» lists before it says how many are left.
INVITEES_SHOWN = 30


def _monthly(referred: int) -> int:
    return get_subscription_price(1, referred)


def overview_html(username: str | None) -> str:
    """How the programme works, with the price ladder and the nick to share."""
    ladder = "\n".join(
        f"{label} — {_monthly(tier)} ₽/мес" for tier, label in enumerate(_TIER_LABELS)
    )
    if username:
        nick = f"Твой ник для друзей: <code>@{escape(username)}</code>"
    else:
        # The bot finds a referrer by Telegram tag, so without one nobody
        # can name you.
        nick = (
            "Чтобы друг мог тебя указать, задай себе имя пользователя в Telegram: "
            "Настройки → Имя пользователя."
        )
    return (
        "🎁 <b>Реферальная программа</b>\n\n"
        "Приглашай друзей — и подписка для тебя дешевеет навсегда.\n\n"
        "<b>Как это работает</b>\n"
        "1. Друг открывает бота, идёт в «🎁 Реф. программа» → «Указать пригласившего» "
        "и вводит твой @ник.\n"
        "2. Как только друг оплатит любую подписку, он засчитается тебе.\n"
        "3. За каждого друга все тарифы для тебя становятся дешевле:\n\n"
        f"{ladder}\n\n"
        "Скидка не сгорает, а на 3–12 месяцев месяц выходит ещё дешевле.\n\n"
        f"{nick}"
    )


def invites_html(user_row, invitees, *, more: bool) -> str:
    """Who invited you, whom you invited, and what your next friend is worth."""
    referrer = (user_row["referrer_tag"] or "").strip()
    if referrer:
        who = f"Тебя пригласил: @{escape(referrer)}"
    else:
        who = "Тебя пригласил: никто. Указать пригласившего можно один раз — на прошлом экране."

    if invitees:
        lines = []
        for row in invitees:
            tag = (row["telegram_tag"] or "").strip()
            name = f"@{escape(tag)}" if tag else "аккаунт с сайта"
            status = "засчитано" if row["is_referred"] else "ждём первую оплату"
            lines.append(f"{'✅' if row['is_referred'] else '⏳'} {name} — {status}")
        if more:
            lines.append("…и другие")
        invited = "<b>Ты пригласил</b>\n" + "\n".join(lines)
    else:
        invited = "<b>Ты пригласил</b>\nПока никто не указал тебя пригласившим."

    credited = int(user_row["referred_people"] or 0)
    price = f"Засчитано: {credited}\nТвоя цена: {_monthly(credited)} ₽/мес"
    if credited < MAX_REFERRAL_TIER:
        price += f"\nЕщё один друг — и будет {_monthly(credited + 1)} ₽/мес"
    else:
        price += "\nЭто максимальная скидка 🎉"

    return f"👥 <b>Мои приглашения</b>\n\n{who}\n\n{invited}\n\n{price}"


async def _show(message: Message, text: str, markup, *, edit: bool) -> None:
    """Over the message the button sits on when it can be, as a new one otherwise."""
    if edit and message.text:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except TelegramBadRequest as exc:
            # The same screen pressed twice: nothing to change, nothing wrong.
            if "message is not modified" not in str(exc):
                raise
        return
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


async def _send_overview(message: Message, user, *, edit: bool) -> None:
    username = getattr(user, "username", None)
    row = await _users.get_user_by_id(user.id)
    can_set = row is not None and not (row["referrer_tag"] or "")
    await _show(message, overview_html(username), referral_keyboard(can_set_referrer=can_set), edit=edit)


@router.message(Command("ref"))
async def referral_program_entry(message: types.Message, state: FSMContext) -> None:
    """/ref: the programme, as from the menu button."""
    await state.clear()
    await _send_overview(message, message.from_user, edit=False)


@router.callback_query(F.data.in_({REFERRAL_CALLBACK, "referral_info"}))
async def referral_program_button(cb: CallbackQuery, state: FSMContext) -> None:
    """
    «🎁 Реф. программа» in the main menu, «🔙 Назад» from the invitations,
    and the retired «ℹ️ О скидках» / reminder buttons (`referral_info`) that
    still sit in old messages -- all open the same screen.
    """
    await state.clear()
    await cb.answer()
    # `cb.message` was sent by the bot, so the person is `cb.from_user`.
    await _send_overview(cb.message, cb.from_user, edit=True)


@router.callback_query(F.data == REFERRAL_INVITES_CALLBACK)
async def referral_invites(cb: CallbackQuery) -> None:
    """«👥 Мои приглашения»."""
    await cb.answer()
    row = await _users.get_user_by_id(cb.from_user.id)
    if row is None:
        await cb.message.answer(
            "Профиль ещё не создан. Откройте /start.", reply_markup=back_to_menu_keyboard()
        )
        return
    invitees = await _users.list_invitees(
        telegram_tag=row["telegram_tag"] or (cb.from_user.username or ""),
        email=row["email"] or "",
        exclude_user_id=str(row["id"]),
        limit=INVITEES_SHOWN + 1,
    )
    text = invites_html(row, invitees[:INVITEES_SHOWN], more=len(invitees) > INVITEES_SHOWN)
    await _show(cb.message, text, referral_invites_keyboard(), edit=True)


@router.callback_query(F.data == "referral_set_tag")
async def referral_set_tag(cb: CallbackQuery, state: FSMContext) -> None:
    # Кнопка остаётся в старых сообщениях: повторное нажатие не должно
    # позволять менять уже указанного пригласившего.
    user_row = await _users.get_user_by_id(cb.from_user.id)
    if user_row and (user_row["referrer_tag"] or ""):
        await cb.answer("Пригласивший уже указан — изменить его нельзя.", show_alert=True)
        return
    await cb.answer()
    await state.set_state(ReferralFSM.waiting_for_tag)
    await cb.message.answer(
        "✍️ Введите @ник пригласившего.\n\n"
        "Можно отменить: /cancel",
        reply_markup=back_to_menu_keyboard(),
    )


@router.message(ReferralFSM.waiting_for_tag)
async def process_referral_nick(message: types.Message, state: FSMContext) -> None:
    tag_raw = message.text.strip()

    if tag_raw.lower() in {"/cancel", "/skip", "отмена"}:
        await message.answer(
            "⏭️ Ввод пригласившего пропущен.",
            reply_markup=back_to_menu_keyboard(),
        )
        await state.clear()
        return

    if tag_raw.startswith("/"):
        await state.clear()
        await message.answer(
            "↩️ Ввод пригласившего отменён.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not tag_raw.startswith("@"):
        await message.answer(
            escape_markdown_v2("Ник должен начинаться с `@`, например `@nickname`\n\n"
                               "Попробуй ещё раз или нажми кнопку ниже"
            ),
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if message.from_user.username and f"@{message.from_user.username.lower()}" == tag_raw.lower():
        await message.answer(
            escape_markdown_v2("Ты не можешь указать сам себя 🙃"),
            parse_mode="MarkdownV2",
        )
        return

    ref_user = await _users.get_user_by_tag(tag_raw[1:])
    if not ref_user:
        await message.answer(
            escape_markdown_v2(
                "Пользователь с таким ником не найден 😕\n\n"
                "Попробуй ещё раз или нажми кнопку ниже"
            ),
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    user_row = await _users.get_user_by_id(message.from_user.id)
    if user_row and (user_row["referrer_tag"] or ""):
        await state.clear()
        await message.answer(
            escape_markdown_v2("Пригласивший уже указан — изменить его нельзя."),
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu_keyboard(),
        )
        return
    await _users.set_referrer_tag(message.from_user.id, tag_raw[1:])
    paid_before = _has_paid_before(user_row)
    if paid_before:
        applied = await _users.award_referral(tag_raw[1:], message.from_user.id)
        if applied:
            text = (
                f"Отлично! Ты указал @{tag_raw[1:]}\n\n"
                "Ты уже оплачивал подписку ранее, поэтому бонус пригласившему начислен сразу ✅"
            )
        else:
            text = (
                f"Отлично! Ты указал @{tag_raw[1:]}\n\n"
                "Реферальный бонус уже был учтён ранее ✅"
            )
    else:
        text = (
            f"Отлично! Ты указал @{tag_raw[1:]}\n\n"
            "Бонус будет начислен другу после твоей оплаты ✅"
        )
    await message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.clear()


@router.message(Command("promo"))
async def promo_code_entry(message: types.Message, state: FSMContext, command: CommandObject) -> None:
    """
    `/promo` alone starts the two-step flow below. `/promo CODE` on one line
    redeems immediately -- the command used to accept and silently discard
    whatever followed it, so a user typing the code they already had lost it
    and was asked to type it again with no explanation.
    """
    args = (command.args or "").strip()
    if args:
        text = await _redeem_promo_code(args.upper(), message.from_user.id)
        await message.answer(text, reply_markup=back_to_menu_keyboard())
        await state.clear()
        return

    await message.answer(
        "🎟️ Введите промокод:",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.set_state(PromoState.waiting_for_promo)


@router.message(PromoState.waiting_for_promo)
async def handle_promo_code(message: Message, state: FSMContext) -> None:
    promo_code = message.text.strip().upper()
    text = await _redeem_promo_code(promo_code, message.from_user.id)
    await message.answer(text, reply_markup=back_to_menu_keyboard())
    await state.clear()


async def _redeem_promo_code(promo_code: str, telegram_id: int) -> str:
    """
    Apply one promo code for one user. Returns the message to show them.

    Shared by both entry points -- typing the code in reply to the prompt,
    and giving it inline as `/promo CODE` -- so the two ways in can never
    validate or credit a code differently from each other.
    """
    promo = await _promo.get_promo_by_code(promo_code)
    if not promo or not promo["is_active"]:
        text = f"❌ Промокод {promo_code} недействителен."
    elif promo["type"] == "gift":
        creator_id_raw = promo["creator_id"] if "creator_id" in promo.keys() else None
        try:
            creator_id = int(creator_id_raw) if creator_id_raw is not None else None
        except (TypeError, ValueError):
            creator_id = None

        # Both handles, matching the website's check. A gift bought on the site
        # records no Telegram ID at all, so comparing that alone let its buyer
        # activate their own code the moment they linked Telegram.
        creator_user_id = (
            promo["creator_user_id"] if "creator_user_id" in promo.keys() else None
        )
        own_row = await _users.get_user_by_id(telegram_id)
        bought_it = (creator_id is not None and creator_id == telegram_id) or (
            creator_user_id is not None
            and own_row is not None
            and str(creator_user_id) == str(own_row["id"])
        )

        if bought_it:
            text = f"❌ Нельзя активировать собственный подарочный промокод {promo_code}."
        elif not await _promo.try_claim_promo_usage(promo_code, telegram_id, one_time=True):
            # Claim до начисления: одноразовый код нельзя погасить дважды,
            # даже если два человека вводят его одновременно.
            text = f"❌ Этот подарочный промокод {promo_code} уже был использован."
        else:
            added_days = promo["value"]
            result = await _extend_subscription_async(telegram_id, added_days)
            if isinstance(result, str) and result.startswith("❌"):
                await _promo.release_promo_usage(promo_code, telegram_id)
                text = f"⚠️ Не удалось продлить подписку: {result}"
            else:
                text = f"✅ Промокод {promo_code} активирован! Подписка продлена на {added_days} дней."
    elif promo["type"] == "days":
        if not await _promo.try_claim_promo_usage(promo_code, telegram_id, one_time=False):
            text = f"❌ Вы уже использовали промокод {promo_code}."
        else:
            added_days = promo["value"]
            result = await _extend_subscription_async(telegram_id, added_days)
            if isinstance(result, str) and result.startswith("❌"):
                await _promo.release_promo_usage(promo_code, telegram_id)
                text = f"⚠️ Не удалось продлить подписку: {result}"
            else:
                text = f"✅ Промокод {promo_code} активирован! Подписка продлена на {added_days} дней."
    else:
        text = f"❌ Тип промокода {promo['type']} пока не поддерживается."

    return text

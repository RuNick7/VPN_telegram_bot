from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from data import db_utils
from data.db_utils import get_user_by_id, get_user_by_tag, set_referrer_tag
from handlers.keyboards import back_to_menu_keyboard, referral_intro_keyboard
from handlers.utils import escape_markdown_v2


router = Router()


class ReferralFSM(StatesGroup):
    waiting_for_tag = State()


class PromoState(StatesGroup):
    waiting_for_promo = State()


@router.message(Command("ref"))
async def referral_program_entry(message: types.Message, state: FSMContext) -> None:
    """
    /ref – выводит инфо о пригласившем (если указан) + сколько людей
    пользователь уже привёл. Если пригласившего нет – пояснение программы
    + статистика «приведённых».
    """
    user = get_user_by_id(message.from_user.id)
    if not user:
        referred_cnt = 0
        await message.answer(
            escape_markdown_v2("Профиль ещё не создан. Используйте /start."),
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu_keyboard(),
        )
        return
    referred_cnt = user["referred_people"] if isinstance(user, dict) else user[6]

    if user["referrer_tag"]:
        text = escape_markdown_v2(
            "📦 Информация о твоём пригласившем\n\n"
            f"👤 Пригласивший: @{user['referrer_tag']}\n"
            "🚫 Изменить его больше нельзя\n\n"
            "Бонус ему начислится после твоей оплаты 💸\n\n"
            f"👥 Ты уже пригласил: {referred_cnt} чел\\."
        )
        await message.answer(
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    intro_text = escape_markdown_v2(
        "🎁 Как работает реферальная программа:\n\n"
        "- Укажи ник друга, который тебя пригласил\n"
        "- После твоей первой оплаты он получит бонус\n"
        "- За каждого друга — дополнительные бонусы и скидки\n\n"
        "✅ Указывать можно только один раз\n\n"
        f"👥 Сейчас у тебя: {referred_cnt} приглашённых"
    )
    await message.answer(
        intro_text,
        parse_mode="MarkdownV2",
        reply_markup=referral_intro_keyboard(),
    )
    await state.set_state(ReferralFSM.waiting_for_tag)


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

    ref_user = get_user_by_tag(tag_raw[1:])
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

    set_referrer_tag(message.from_user.id, tag_raw[1:])
    await message.answer(
        escape_markdown_v2(
            f"Отлично! Ты указал @{tag_raw[1:]}\n\nБонус будет начислен другу после твоей оплаты ✅"
        ),
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.clear()


@router.callback_query(F.data == "referral_info")
async def referral_info(cb: CallbackQuery) -> None:
    """
    Показ реферальной программы.
    Никаких видео или chat_action — только текст и клавиатура.
    """
    text = (
        "🎁 *Реферальная программа*\n\n"
        "Приглашай друзей и получай скидки на все тарифы 💸\n"
        "Чем больше друзей — тем ниже цена подписки 👥\n\n"
        "✅ Скидки сочетаются с длительностью подписки: чем дольше срок — тем дешевле один месяц\n\n"
        "📘 Полная таблица цен и примеры расчётов доступны на сайте:\n"
        "https://nitravpn.gitbook.io/nitravpn/referalnaya-programma"
    )

    await cb.answer()
    await cb.message.answer(
        escape_markdown_v2(text),
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu_keyboard(),
        disable_web_page_preview=False,
    )


@router.message(Command("promo"))
async def promo_code_entry(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        "🎟️ Введите промокод:",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.set_state(PromoState.waiting_for_promo)


@router.message(PromoState.waiting_for_promo)
async def handle_promo_code(message: Message, state: FSMContext) -> None:
    promo_code = message.text.strip().upper()
    telegram_id = message.from_user.id
    escaped_code = escape_markdown_v2(promo_code)

    promo = db_utils.get_promo_by_code(promo_code)
    if not promo or not promo["is_active"]:
        text = f"❌ Промокод *{escaped_code}* недействителен\\."
    elif promo["type"] == "gift":
        if int(promo["creator_id"]) == telegram_id:
            text = f"❌ Нельзя активировать собственный подарочный промокод *{escaped_code}*\\."
        elif db_utils.has_any_usage(promo_code):
            text = f"❌ Этот подарочный промокод *{escaped_code}* уже был использован\\."
        else:
            added_days = promo["value"]
            from app.services.remnawave import vpn_service as vpn
            result = vpn.extend_subscription_by_telegram_id(telegram_id, added_days)
            if isinstance(result, str) and result.startswith("❌"):
                text = f"⚠️ Не удалось продлить подписку: {result}"
            else:
                db_utils.save_promo_usage(promo_code, telegram_id)
                text = f"✅ Промокод *{escaped_code}* активирован\\! Подписка продлена на *{added_days}* дней\\."
    elif db_utils.has_used_promo(promo_code, telegram_id):
        text = f"❌ Вы уже использовали промокод *{escaped_code}*\\."
    else:
        if promo["type"] == "days":
            added_days = promo["value"]
            from app.services.remnawave import vpn_service as vpn
            result = vpn.extend_subscription_by_telegram_id(telegram_id, added_days)
            if isinstance(result, str) and result.startswith("❌"):
                text = f"⚠️ Не удалось продлить подписку: {result}"
            else:
                text = f"✅ Промокод *{escaped_code}* активирован\\! Подписка продлена на *{added_days}* дней\\."
        else:
            text = f"❌ Тип промокода *{promo['type']}* пока не поддерживается\\."

        if not text.startswith("⚠️"):
            db_utils.save_promo_usage(promo_code, telegram_id)

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.clear()

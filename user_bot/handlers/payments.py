import logging
import traceback

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from data import db_utils
from data.db_utils import get_user_by_id
from handlers.keyboards import (
    gift_payment_keyboard,
    gift_tariffs_keyboard,
    payment_keyboard,
    tariff_menu_keyboard,
)
from handlers.utils import get_subscription_price
from payments.yookassa_client import create_payment


router = Router()


async def _send_tariff_menu(
    target: types.Message | types.CallbackQuery,
    *,
    as_edit: bool = False,
) -> None:
    tg_id = target.from_user.id
    usr = db_utils.get_user_by_id(tg_id)
    ref_count = usr["referred_people"] if usr else 0

    tariffs = {
        1: {"duration": "1 месяц", "months": 1},
        3: {"duration": "3 месяца", "months": 3},
        6: {"duration": "6 месяцев", "months": 6},
        12: {"duration": "1 год", "months": 12},
    }

    buttons: list[tuple[str, str]] = []
    for _, info in sorted(tariffs.items()):
        months = info["months"]
        try:
            price = get_subscription_price(months, ref_count)
        except Exception as exc:
            logging.error("[ERROR] Цена для %s мес., ref=%s: %s", months, ref_count, exc)
            price = "?"

        buttons.append((f"{info['duration']} — {price}₽", f"buy_tariff:{months}"))

    kb = tariff_menu_keyboard(buttons)
    text_md = "📦 *Выберите тариф*:\n"

    if as_edit:
        await target.message.edit_text(text_md, reply_markup=kb, parse_mode="MarkdownV2")
        await target.answer()
    else:
        if isinstance(target, types.CallbackQuery):
            await target.answer()
            await target.message.answer(text_md, reply_markup=kb, parse_mode="MarkdownV2")
        else:
            await target.answer(text_md, reply_markup=kb, parse_mode="MarkdownV2")

    logging.info("[INFO] Тарифы показаны %s, рефералов: %s", tg_id, ref_count)


@router.message(Command("pay"))
async def subscription_tariffs_cmd(message: types.Message) -> None:
    await _send_tariff_menu(message, as_edit=False)


@router.callback_query(F.data == "subscription")
async def subscription_back_cb(cb: CallbackQuery) -> None:
    await _send_tariff_menu(cb, as_edit=False)


@router.callback_query(F.data == "subscription_tariffs")
async def subscription_tariffs_cb(cb: CallbackQuery) -> None:
    await _send_tariff_menu(cb, as_edit=False)


@router.callback_query(lambda c: c.data.startswith("buy_tariff:"))
async def buy_tariff_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()

    try:
        data = callback_query.data.split(":")
        months = int(data[1])
    except Exception as exc:
        logging.error("[ERROR] Некорректные данные тарифа: %s - %s", callback_query.data, exc)
        await callback_query.message.edit_text("❌ Ошибка: некорректный тариф.")
        return

    if months not in (1, 3, 6, 12):
        await callback_query.message.edit_text("❌ Ошибка: выбран неизвестный тариф.")
        return

    telegram_id = callback_query.from_user.id
    user = db_utils.get_user_by_id(telegram_id)
    referred_people = user["referred_people"] if user else 0

    try:
        amount = get_subscription_price(months, referred_people)
    except Exception as exc:
        logging.error("[ERROR] Не удалось получить цену: %s", exc)
        await callback_query.message.edit_text("❌ Ошибка при определении цены.")
        return

    description = f"Оплата подписки на {months} мес\\. с {referred_people} реферал(ов)"
    return_url = "https://t.me/NitraTunnel_Bot"
    days_to_add = months * 30

    try:
        payment = create_payment(
            amount=amount,
            description=description,
            return_url=return_url,
            telegram_id=telegram_id,
            days_to_extend=days_to_add,
        )
        confirmation_url = payment.confirmation.confirmation_url

        await callback_query.message.edit_text(
            "Нажмите кнопку ниже для перехода к оплате\n"
            "После оплаты вам придёт уведомление в боте и подписка автоматически продлиться",
            reply_markup=payment_keyboard(confirmation_url),
            parse_mode="MarkdownV2",
        )

        logging.info(
            "[INFO] Платёж создан: telegram_id=%s, месяцев=%s, цена=%s₽",
            telegram_id,
            months,
            amount,
        )
    except Exception as exc:
        traceback.print_exc()
        logging.error("[ERROR] Ошибка создания платежа для telegram_id %s: %s", telegram_id, exc)
        await callback_query.message.edit_text(f"❌ Ошибка при создании платежа: {exc}")


@router.message(Command("gift"))
async def gift_subscription_cmd(message: types.Message) -> None:
    """
    Показывает тарифы для подарочной подписки + статистику:
    сколько подписок пользователь уже подарил.
    """
    user_row = get_user_by_id(message.from_user.id)
    if not user_row:
        gifted = 0
    else:
        gifted = user_row["gifted_subscriptions"] if isinstance(user_row, dict) else user_row[5]

    tariffs = {
        1: {"duration": "1 месяц", "price": 89},
        3: {"duration": "3 месяца", "price": 249},
        6: {"duration": "6 месяцев", "price": 479},
        12: {"duration": "1 год", "price": 899},
    }

    text_md = (
        "🎁 *Подарить подписку другу*\n\n"
        "Мы сгенерируем специальный промокод, который ваш друг сможет ввести в боте и получить доступ\\.\n\n"
        f"_У тебя уже подарено_: *{gifted}* _подписок_"
        f"*Выберите срок подарка:*\n\n"
    )

    await message.answer(
        text_md,
        reply_markup=gift_tariffs_keyboard(tariffs),
        parse_mode="MarkdownV2",
    )


@router.callback_query(F.data == "gift_subscription")
async def gift_subscription_cb(cb: CallbackQuery) -> None:
    user_row = get_user_by_id(cb.from_user.id)
    if not user_row:
        gifted = 0
    else:
        gifted = user_row["gifted_subscriptions"] if isinstance(user_row, dict) else user_row[5]

    tariffs = {
        1: {"duration": "1 месяц", "price": 89},
        3: {"duration": "3 месяца", "price": 249},
        6: {"duration": "6 месяцев", "price": 479},
        12: {"duration": "1 год", "price": 899},
    }

    text_md = (
        "🎁 *Подарить подписку другу*\n\n"
        "Мы сгенерируем специальный промокод, который ваш друг сможет ввести в боте и получить доступ\\.\n\n"
        f"_У тебя уже подарено_: *{gifted}* _подписок_"
        f"*Выберите срок подарка:*\n\n"
    )
    await cb.answer()
    await cb.message.answer(
        text_md,
        reply_markup=gift_tariffs_keyboard(tariffs),
        parse_mode="MarkdownV2",
    )


@router.callback_query(lambda c: c.data.startswith("buy_gift:"))
async def buy_gift_callback(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        months = int(callback.data.split(":")[1])
    except Exception as exc:
        logging.error("[ERROR] Некорректный формат buy_gift: %s — %s", callback.data, exc)
        await callback.message.edit_text("❌ Ошибка: неверный формат запроса.")
        return

    gift_tariffs = {
        1: {"duration": "1 месяц", "price": 89, "days": 30},
        3: {"duration": "3 месяца", "price": 249, "days": 90},
        6: {"duration": "6 месяцев", "price": 479, "days": 180},
        12: {"duration": "1 год", "price": 899, "days": 365},
    }

    if months not in gift_tariffs:
        await callback.message.edit_text("❌ Такой подарок не найден.")
        return

    gift = gift_tariffs[months]
    telegram_id = callback.from_user.id
    description = f"Подарочная подписка на {gift['duration']}"
    return_url = "https://yourdomain.com/return"

    try:
        payment = create_payment(
            amount=gift["price"],
            description=description,
            return_url=return_url,
            telegram_id=telegram_id,
            days_to_extend=gift["days"],
            is_gift=True,
        )
        url = payment.confirmation.confirmation_url

        await callback.message.edit_text(
            "🎁 Для оформления подарка нажмите на кнопку ниже:",
            reply_markup=gift_payment_keyboard(url),
        )
    except Exception as exc:
        logging.exception("[GIFT ERROR] Ошибка создания платежа: %s", exc)
        await callback.message.edit_text("❌ Не удалось создать платёж. Попробуйте позже.")

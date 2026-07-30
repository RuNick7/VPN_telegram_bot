import asyncio
import logging
import time
import traceback

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from tgvpn_shared.settings import get_settings
from tgvpn_shared.db import LteRepository, UserRepository
from tgvpn_shared.lte_quota import TRAFFIC_LABEL, format_traffic, remaining_now
from handlers.constants import LTE_TRAFFIC_PACKS
from handlers.keyboards import (
    gift_payment_keyboard,
    gift_tariffs_keyboard,
    lte_packs_keyboard,
    lte_payment_keyboard,
    payment_keyboard,
    renew_menu_keyboard,
    tariff_menu_keyboard,
)
from handlers.utils import get_subscription_price, subscription_label
from payments.yookassa_client import create_payment


router = Router()
_users = UserRepository()
_lte = LteRepository()

# Жёсткий потолок на синхронный YooKassa SDK (Payment.create использует requests).
# Без этого один залипший запрос блокирует весь polling-бот.
YOOKASSA_CREATE_TIMEOUT_SECONDS = 15.0


async def _create_payment_async(**kwargs):
    """Запускаем sync YooKassa SDK в thread-pool с таймаутом."""
    return await asyncio.wait_for(
        asyncio.to_thread(create_payment, **kwargs),
        timeout=YOOKASSA_CREATE_TIMEOUT_SECONDS,
    )


# Куда YooKassa возвращает пользователя после оплаты — обратно в наш бот.
_BOT_USERNAME = get_settings().telegram_bot_username.strip().lstrip("@")
PAYMENT_RETURN_URL = f"https://t.me/{_BOT_USERNAME}" if _BOT_USERNAME else "https://t.me"


async def _send_tariff_menu(
    target: types.Message | types.CallbackQuery,
    *,
    as_edit: bool = False,
) -> None:
    tg_id = target.from_user.id
    usr = await _users.get_user_by_id(tg_id)
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

        label = (
            subscription_label(info["duration"], months, price, ref_count)
            if isinstance(price, int)
            else f"{info['duration']} — {price}₽"
        )
        buttons.append((label, f"buy_tariff:{months}"))

    kb = tariff_menu_keyboard(buttons, with_traffic=get_settings().lte_enabled)
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


async def _send_renew_menu(target: types.Message | CallbackQuery) -> None:
    """
    Offer both things a user can buy, instead of assuming they want a plan.

    Someone whose subscription lapsed may want servers back; someone who ran
    out of metered traffic wants gigabytes. Jumping straight to plans made the
    second case a dead end.
    """
    settings = get_settings()
    text = "💳 <b>Что продлить?</b>"
    if settings.lte_enabled:
        text += (
            "\n\n<b>Подписка</b> — доступ ко всем серверам.\n"
            f"<b>{TRAFFIC_LABEL}</b> — дополнительные ГБ на серверах "
            "с ограниченным трафиком."
        )
    keyboard = renew_menu_keyboard(with_traffic=settings.lte_enabled)

    if isinstance(target, CallbackQuery):
        await target.answer()
        await target.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("pay"))
async def pay_cmd(message: types.Message) -> None:
    await _send_renew_menu(message)


@router.callback_query(F.data == "renew_menu")
async def renew_menu_cb(cb: CallbackQuery) -> None:
    await _send_renew_menu(cb)


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
    user = await _users.get_user_by_id(telegram_id)
    referred_people = user["referred_people"] if user else 0

    try:
        amount = get_subscription_price(months, referred_people)
    except Exception as exc:
        logging.error("[ERROR] Не удалось получить цену: %s", exc)
        await callback_query.message.edit_text("❌ Ошибка при определении цены.")
        return

    description = f"Оплата подписки на {months} мес. с {referred_people} реферал(ов)"
    return_url = PAYMENT_RETURN_URL
    days_to_add = months * 30

    try:
        payment = await _create_payment_async(
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
    except asyncio.TimeoutError:
        logging.error("[ERROR] Таймаут создания платежа: telegram_id=%s months=%s", telegram_id, months)
        await callback_query.message.edit_text(
            "❌ YooKassa слишком долго не отвечает. Попробуйте через минуту."
        )
    except Exception as exc:
        traceback.print_exc()
        logging.error("[ERROR] Ошибка создания платежа для telegram_id %s: %s", telegram_id, exc)
        await callback_query.message.edit_text(f"❌ Ошибка при создании платежа: {exc}")


# -- LTE traffic packs ------------------------------------------------------


async def _send_lte_packs(target: types.Message | CallbackQuery) -> None:
    """
    Show traffic packs, with the user's current balance for context.

    Prices are flat -- deliberately outside the referral discount ladder that
    applies to subscriptions, since traffic is a consumable resold at cost.
    """
    telegram_id = target.from_user.id
    state = await _lte.get_state(telegram_id)
    balance_gb = (int(state["lte_paid_balance_bytes"] or 0) / 1024**3) if state else 0.0

    settings = get_settings()
    override = state.get("lte_free_gb_override") if state else None
    free_gb = override if override is not None else settings.lte_free_gb_per_cycle

    # Same figure the devices menu shows, from the same helper -- two screens
    # quoting different balances would just look broken.
    left = (
        remaining_now(
            state=state,
            global_free_gb=settings.lte_free_gb_per_cycle,
            cycle_seconds=settings.lte_cycle_seconds,
            now=int(time.time()),
        )
        if state
        else 0
    )

    text = (
        f"📶 <b>{TRAFFIC_LABEL}</b>\n\n"
        f"Осталось сейчас: <b>{format_traffic(left)}</b>\n"
        f"Бесплатно каждый месяц: <b>{free_gb} ГБ</b>\n"
        f"Куплено сверх лимита: <b>{balance_gb:.2f} ГБ</b>\n\n"
        "Купленный трафик не сгорает и переходит на следующий месяц.\n"
        "Цена за ГБ фиксированная и не зависит от количества приглашённых.\n\n"
        "Выберите пакет:"
    )
    keyboard = lte_packs_keyboard(LTE_TRAFFIC_PACKS)

    if isinstance(target, CallbackQuery):
        await target.answer()
        await target.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("traffic"))
async def lte_packs_cmd(message: types.Message) -> None:
    await _send_lte_packs(message)


@router.callback_query(F.data == "lte_packs")
async def lte_packs_cb(cb: CallbackQuery) -> None:
    await _send_lte_packs(cb)


@router.callback_query(F.data.startswith("buy_lte:"))
async def buy_lte_callback(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        gigabytes = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        logging.error("[LTE] Некорректный формат buy_lte: %s", callback.data)
        await callback.message.edit_text("❌ Ошибка: некорректный пакет.")
        return

    # Price comes from the table, never from the callback -- the callback is
    # user-controlled and a spoofed one must not be able to name its own price.
    price = LTE_TRAFFIC_PACKS.get(gigabytes)
    if price is None:
        await callback.message.edit_text("❌ Такой пакет не найден.")
        return

    telegram_id = callback.from_user.id
    try:
        payment = await _create_payment_async(
            amount=price,
            description=f"{TRAFFIC_LABEL}: {gigabytes} ГБ",
            return_url=PAYMENT_RETURN_URL,
            telegram_id=telegram_id,
            # Traffic purchases must not touch the subscription date; the
            # webhook branches on lte_gb and leaves days_to_extend unused.
            days_to_extend=0,
            lte_gb=gigabytes,
        )
        await callback.message.edit_text(
            f"📶 {TRAFFIC_LABEL}: пакет {gigabytes} ГБ за {price}₽.\n\n"
            "Нажмите кнопку ниже для оплаты — трафик начислится автоматически.",
            reply_markup=lte_payment_keyboard(payment.confirmation.confirmation_url),
        )
        logging.info("[LTE] Платёж создан: telegram_id=%s gb=%s price=%s₽",
                     telegram_id, gigabytes, price)
    except asyncio.TimeoutError:
        logging.error("[LTE] Таймаут создания платежа: telegram_id=%s gb=%s", telegram_id, gigabytes)
        await callback.message.edit_text(
            "❌ YooKassa слишком долго не отвечает. Попробуйте через минуту."
        )
    except Exception as exc:
        logging.exception("[LTE] Ошибка создания платежа: %s", exc)
        await callback.message.edit_text("❌ Не удалось создать платёж. Попробуйте позже.")


@router.message(Command("gift"))
async def gift_subscription_cmd(message: types.Message) -> None:
    """
    Показывает тарифы для подарочной подписки + статистику:
    сколько подписок пользователь уже подарил.
    """
    user_row = await _users.get_user_by_id(message.from_user.id)
    gifted = int(user_row["gifted_subscriptions"] or 0) if user_row else 0

    tariffs = {
        1: {"duration": "1 месяц", "price": 89},
        3: {"duration": "3 месяца", "price": 249},
        6: {"duration": "6 месяцев", "price": 479},
        12: {"duration": "1 год", "price": 899},
    }

    text_md = (
        "🎁 *Подарить подписку другу*\n\n"
        "Мы сгенерируем специальный промокод, который ваш друг сможет ввести в боте и получить доступ\\.\n\n"
        f"_У тебя уже подарено_: *{gifted}* _подписок_\n\n"
        f"*Выберите срок подарка:*\n\n"
    )

    await message.answer(
        text_md,
        reply_markup=gift_tariffs_keyboard(tariffs),
        parse_mode="MarkdownV2",
    )


@router.callback_query(F.data == "gift_subscription")
async def gift_subscription_cb(cb: CallbackQuery) -> None:
    user_row = await _users.get_user_by_id(cb.from_user.id)
    gifted = int(user_row["gifted_subscriptions"] or 0) if user_row else 0

    tariffs = {
        1: {"duration": "1 месяц", "price": 89},
        3: {"duration": "3 месяца", "price": 249},
        6: {"duration": "6 месяцев", "price": 479},
        12: {"duration": "1 год", "price": 899},
    }

    text_md = (
        "🎁 *Подарить подписку другу*\n\n"
        "Мы сгенерируем специальный промокод, который ваш друг сможет ввести в боте и получить доступ\\.\n\n"
        f"_У тебя уже подарено_: *{gifted}* _подписок_\n\n"
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
    return_url = PAYMENT_RETURN_URL

    try:
        payment = await _create_payment_async(
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
    except asyncio.TimeoutError:
        logging.error("[GIFT ERROR] Таймаут создания платежа: telegram_id=%s", telegram_id)
        await callback.message.edit_text(
            "❌ YooKassa слишком долго не отвечает. Попробуйте через минуту."
        )
    except Exception as exc:
        logging.exception("[GIFT ERROR] Ошибка создания платежа: %s", exc)
        await callback.message.edit_text("❌ Не удалось создать платёж. Попробуйте позже.")

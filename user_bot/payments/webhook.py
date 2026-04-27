import asyncio
import logging
import os

import aiohttp as _aiohttp
from aiohttp import web
from yookassa.domain.notification import WebhookNotification

from app.services.remnawave.vpn_service import extend_subscription_by_telegram_id
from bot import bot
from data import db_utils
from data.db_utils import (
    add_lte_paid_gb,
    generate_gift_code,
    get_payment_status,
    update_payment_status,
)
from handlers.utils import escape_markdown_v2
from payments.yookassa_client import fetch_payment

ADMIN_ID = int((os.getenv("ADMIN_IDS") or "").split(",")[0].strip() or "0")
logger = logging.getLogger(__name__)

# Жёсткие потолки на блокирующие сетевые вызовы, чтобы зависший
# upstream (YooKassa/Remnawave) никогда не клал event loop надолго.
YOOKASSA_FETCH_TIMEOUT_SECONDS = 15.0
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0
REQUEST_BODY_TIMEOUT_SECONDS = 10.0

# Web-кабинет: push-уведомления через internal API (loopback).
WEB_INTERNAL_PUSH_URL = (
    os.getenv("WEB_INTERNAL_PUSH_URL")
    or f"{(os.getenv('API_BASE_URL') or 'http://127.0.0.1:8001').rstrip('/')}"
    "/api/internal/push/send"
)
WEB_INTERNAL_SECRET = (os.getenv("WEB_INTERNAL_SECRET") or "").strip()
WEB_PUSH_TIMEOUT_SECONDS = 5.0


async def _try_send_web_push(
    *,
    telegram_id: int,
    title: str,
    body: str,
    url: str = "/cabinet",
    tag: str = "kaira-default",
) -> None:
    """Best-effort web-push notification. Никогда не роняет webhook."""
    if not WEB_INTERNAL_SECRET:
        return
    try:
        timeout = _aiohttp.ClientTimeout(total=WEB_PUSH_TIMEOUT_SECONDS)
        async with _aiohttp.ClientSession(timeout=timeout) as session:
            await session.post(
                WEB_INTERNAL_PUSH_URL,
                json={
                    "telegram_id": int(telegram_id),
                    "title": title,
                    "body": body,
                    "url": url,
                    "tag": tag,
                },
                headers={"X-Kaira-Internal-Secret": WEB_INTERNAL_SECRET},
            )
    except Exception as exc:
        logger.warning("web-push send failed for %s: %s", telegram_id, exc)


async def _send_markdown_or_plain(chat_id: int, text: str) -> None:
    """Try MarkdownV2 first; fallback to plain text."""
    try:
        await bot.send_message(chat_id, text, parse_mode="MarkdownV2")
    except Exception as exc:
        logger.warning("MarkdownV2 send failed for %s, fallback to plain text: %s", chat_id, exc)
        await bot.send_message(chat_id, text.replace("\\", ""))


async def yookassa_webhook_handler(request: web.Request):
    logger.info("Получен запрос вебхука от Yookassa.")
    try:
        payload = await asyncio.wait_for(
            request.json(),
            timeout=REQUEST_BODY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Webhook body read timeout after %ss", REQUEST_BODY_TIMEOUT_SECONDS)
        return web.json_response({"error": "Body read timeout"}, status=408)
    except Exception as e:
        logger.error("Ошибка при разборе JSON: %s", e)
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        # Парсим уведомление от Юкассы
        notification = WebhookNotification(payload)
    except Exception as e:
        return web.Response(status=400, text=f"Ошибка обработки уведомления: {e}")

    event = notification.event              # Например, "payment.succeeded"
    payment = notification.object           # Сам объект платежа
    if payment is None:
        logger.warning("Webhook payload has no payment object: %s", payload)
        return web.json_response({"error": "Invalid payload: missing payment object"}, status=400)

    payment_id = getattr(payment, "id", None)  # Идентификатор платежа в YooKassa
    if not payment_id:
        logger.warning("Webhook payload has no payment.id: %s", payload)
        return web.json_response({"error": "Invalid payload: missing payment id"}, status=400)

    # YooKassa SDK синхронный (использует requests). Уносим его в thread-pool,
    # чтобы не блокировать event loop, и накладываем жёсткий таймаут.
    payment_api = None
    try:
        payment_api = await asyncio.wait_for(
            asyncio.to_thread(fetch_payment, payment_id),
            timeout=YOOKASSA_FETCH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "YooKassa fetch_payment timeout (>%ss) для %s",
            YOOKASSA_FETCH_TIMEOUT_SECONDS,
            payment_id,
        )
        if ADMIN_ID:
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⏱ YooKassa API timeout для платежа {payment_id}",
                )
            except Exception as send_err:
                logger.error("Ошибка отправки админу: %s", send_err)
    except Exception as e:
        logger.error("Не удалось запросить платеж %s из YooKassa: %s", payment_id, e)
        if ADMIN_ID:
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"❌ YooKassa API error для платежа {payment_id}: {e}",
                )
            except Exception as send_err:
                logger.error("Ошибка отправки админу: %s", send_err)

    effective_payment = payment_api or payment
    effective_status = getattr(effective_payment, "status", None)

    if event == "payment.succeeded" or effective_status == "succeeded":
        logger.info("Платёж успешно завершён: %s", payment_id)

        existing_status = await asyncio.to_thread(get_payment_status, payment_id)
        if existing_status == "succeeded":
            logger.info("Платёж %s уже обработан. Пропуск.", payment_id)
            return web.json_response({"status": "ok"}, status=200)

        # Считываем данные из metadata
        metadata = (getattr(effective_payment, "metadata", None) or {}) if effective_payment else {}
        telegram_id_raw = metadata.get("telegram_id")
        try:
            telegram_id = int(telegram_id_raw) if telegram_id_raw is not None else None
        except (TypeError, ValueError):
            telegram_id = None
        days_to_extend = metadata.get("days_to_extend", 30)
        is_gift_raw = metadata.get("is_gift", False)
        purchase_type = str(metadata.get("purchase_type") or "").strip().lower()
        lte_gb_raw = metadata.get("lte_gb", 0)

        try:
            days_to_extend = int(days_to_extend)
        except (TypeError, ValueError):
            logger.warning("Некорректный days_to_extend=%s, используем 30", days_to_extend)
            days_to_extend = 30

        if days_to_extend <= 0:
            logger.warning("days_to_extend=%s <= 0, используем 30", days_to_extend)
            days_to_extend = 30

        if isinstance(is_gift_raw, bool):
            is_gift = is_gift_raw
        else:
            is_gift = str(is_gift_raw).strip().lower() in {"true", "1", "yes", "y"}

        logger.info("Платёж успешен. telegram_id: %s, days_to_extend: %s", telegram_id, days_to_extend)

        if telegram_id:
            result = ""
            user_message = ""
            group_message = ""

            if purchase_type == "lte_gb":
                try:
                    lte_gb = int(lte_gb_raw)
                except (TypeError, ValueError):
                    lte_gb = 0
                if lte_gb <= 0:
                    logger.warning("Некорректный lte_gb в metadata: %s", lte_gb_raw)
                    user_message = (
                        "⚠️ Платёж прошёл, но пакет LTE ГБ не удалось определить.\n"
                        "Пожалуйста, напишите в поддержку."
                    )
                    group_message = (
                        f"⚠️ LTE-платёж без валидного lte_gb\n"
                        f"Пользователь: {telegram_id}\n"
                        f"payment_id: {payment_id}"
                    )
                else:
                    await asyncio.to_thread(add_lte_paid_gb, telegram_id, lte_gb)
                    result = f"LTE +{lte_gb} ГБ"
                    user_message = (
                        f"✅ Ваш платеж успешно завершен\\!\n"
                        f"Добавлено *{lte_gb} ГБ LTE трафика*\\.\n\n"
                        "📌 Пакет действует только для LTE серверов с лимитом\\.\n"
                        "♻️ Непотраченные LTE ГБ переносятся на следующий месяц\\."
                    )
                    group_message = (
                        f"📶 LTE пакет успешно оплачен\n"
                        f"Пользователь: {telegram_id}\n"
                        f"Добавлено: {lte_gb} ГБ"
                    )
            elif is_gift:
                # 🎁 Генерация подарочного кода
                gift_code = await asyncio.to_thread(generate_gift_code)
                escape_gift_code = escape_markdown_v2(gift_code)
                await asyncio.to_thread(
                    db_utils.create_gift_promo, gift_code, days_to_extend, telegram_id
                )
                # Увеличиваем счётчик
                try:
                    await asyncio.to_thread(db_utils.increment_gifted_subscriptions, telegram_id)
                    logger.info(f"[GIFT] Пользователь {telegram_id} теперь подарил ещё одну подписку.")
                except Exception as e:
                    logger.error(f"[GIFT] Не удалось обновить gifted_subscriptions для {telegram_id}: {e}")

                # Формируем текст
                result = f"🎁 Промокод для подарка: `{escape_gift_code}`"
                user_message = (
                    f"✅ Платёж успешно завершен\\!\n"
                    f"Вы приобрели *подарочную подписку* на *{days_to_extend}* дней\\.\n\n"
                    f"Передайте другу этот код: `{escape_gift_code}`"
                )
                group_message = (
                    f"🎁 Подарок оформлен\\!\n"
                    f"Пользователь: {telegram_id}\n"
                    f"Срок: {days_to_extend} дней\n"
                    f"Код: {escape_gift_code}"
                )
            else:
                # 📦 Продлеваем подписку (sync HTTP в Remnawave) — выносим в thread
                # с жёстким таймаутом, чтобы зависший Remnawave не клал webhook.
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            extend_subscription_by_telegram_id,
                            telegram_id,
                            days_to_extend,
                        ),
                        timeout=REMNAWAVE_EXTEND_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    result = (
                        f"❌ Таймаут продления подписки (>{REMNAWAVE_EXTEND_TIMEOUT_SECONDS}s)"
                    )
                    logger.error(
                        "extend_subscription_by_telegram_id timeout for %s",
                        telegram_id,
                    )
                logger.info("Результат продления подписки: %s", result)

                # ✅ Проверка на реферала
                try:
                    user = await asyncio.to_thread(db_utils.get_user_by_id, telegram_id)
                    if user and user["referrer_tag"]:
                        applied = await asyncio.to_thread(
                            db_utils.award_referral,
                            user["referrer_tag"],
                            telegram_id,
                        )
                        if applied:
                            logger.info(f"[Referral] Зачислен реферал: @{user['referrer_tag']} от {telegram_id}")
                        else:
                            logger.info(f"[Referral] Уже начислен: {telegram_id}")
                    else:
                        logger.info(f"[Referral] Не начислен: {telegram_id}")
                except Exception as e:
                    logger.exception(f"[Referral] Ошибка: {e}")

                if isinstance(result, str) and result.startswith("❌"):
                    user_message = (
                        "⚠️ Платёж прошёл, но при продлении возникла ошибка.\n"
                        "Мы уже занимаемся этим вопросом."
                    )
                    group_message = (
                        f"⚠️ Ошибка продления\n"
                        f"Пользователь: {telegram_id}\n"
                        f"Текст: {result}"
                    )
                else:
                    user_message = (
                        f"✅ Ваш платеж успешно завершен\n"
                        f"Подписка продлена на {days_to_extend} дней\n\n"
                    )
                    group_message = (
                        f"🔔 Платеж успешно завершен\n"
                        f"Пользователь: {telegram_id}\n"
                        f"Тариф продлен на {days_to_extend} дней"
                    )

            # ✅ Обновляем статус
            await asyncio.to_thread(update_payment_status, payment_id, "succeeded")

            # 🔔 Web push (best-effort, не блокирует на ошибках)
            if purchase_type == "lte_gb":
                try:
                    lte_gb = int(lte_gb_raw)
                except (TypeError, ValueError):
                    lte_gb = 0
                if lte_gb > 0:
                    await _try_send_web_push(
                        telegram_id=telegram_id,
                        title="LTE-пакет зачислен",
                        body=f"+{lte_gb} ГБ LTE на 30 дней",
                        url="/cabinet/lte",
                        tag="kaira-payment",
                    )
            elif is_gift:
                await _try_send_web_push(
                    telegram_id=telegram_id,
                    title="Подарочный код готов",
                    body=f"Подписка на {days_to_extend} дней — отправьте другу",
                    url="/cabinet/gifts",
                    tag="kaira-gift",
                )
            else:
                if not (isinstance(result, str) and result.startswith("❌")):
                    await _try_send_web_push(
                        telegram_id=telegram_id,
                        title="Подписка продлена",
                        body=f"Срок подписки увеличен на {days_to_extend} дней",
                        url="/cabinet",
                        tag="kaira-payment",
                    )

            # 🔔 Уведомления
            try:
                await _send_markdown_or_plain(telegram_id, user_message)
                logger.info("Сообщение пользователю отправлено")
            except Exception as e:
                logger.error("Ошибка отправки сообщения пользователю: %s", e)

            if ADMIN_ID:
                try:
                    await _send_markdown_or_plain(ADMIN_ID, group_message)
                    logger.info("Сообщение админу отправлено")
                except Exception as e:
                    logger.error("Ошибка отправки сообщения админу: %s", e)
            else:
                logger.warning("ADMIN_IDS не задан, уведомление админу не отправлено")
        else:
            logger.warning("telegram_id не найден в metadata.")
    else:
        logger.info("Получено событие '%s'. Обработка не требуется.", event)
    # Можно обрабатывать и другие события (payment.waiting_for_capture и т.д.),
    # но чаще достаточно только payment.succeeded
    return web.json_response({"status": "ok"}, status=200)

# Дорогой прогер:
#
# Когда ты закончишь «оптимизировать» эту подпрограмму
# и поймешь, насколько большой ошибкой было делать это,
# пожалуйста, увеличь счетчик внизу как предупреждение
# для следующего парня:
#
# total_hours_wasted_here = 8

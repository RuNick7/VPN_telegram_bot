import asyncio
import logging
import os

from aiohttp import web
from yookassa.domain.notification import WebhookNotification

from app.services.remnawave.vpn_service import extend_subscription_by_telegram_id
from bot import bot
from tgvpn_shared.db import PaymentRepository, PromoRepository, UserRepository, generate_gift_code
from handlers.utils import escape_markdown_v2
from payments.yookassa_client import fetch_payment

ADMIN_ID = int((os.getenv("ADMIN_IDS") or "").split(",")[0].strip() or "0")
logger = logging.getLogger(__name__)

_users = UserRepository()
_payments = PaymentRepository()
_promo = PromoRepository()

# Жёсткие потолки на блокирующие сетевые вызовы, чтобы зависший
# upstream (YooKassa/Remnawave) никогда не клал event loop надолго.
YOOKASSA_FETCH_TIMEOUT_SECONDS = 15.0
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0
REQUEST_BODY_TIMEOUT_SECONDS = 10.0


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
    #
    # БЕЗОПАСНОСТЬ: notification.event/notification.object — это тело запроса,
    # его не проверяет никто (подписи/секрета у вебхука нет). Единственный
    # источник правды о статусе платежа — прямой ответ YooKassa на fetch по
    # payment_id. Если запрос не удался — обрываем обработку, а не работаем
    # дальше на основе непроверенных данных из запроса: иначе любой, кто знает
    # URL вебхука, может подделать payment_id/status/metadata и получить
    # бесплатное продление подписки или подарочный код.
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
        return web.json_response({"error": "Upstream verification timeout"}, status=504)
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
        return web.json_response({"error": "Upstream verification failed"}, status=502)

    # effective_status/metadata ниже всегда берутся из payment_api (проверенный
    # ответ YooKassa), а не из notification.object. `event` из тела запроса
    # больше не участвует в решении о начислении — используется только для лога.
    effective_payment = payment_api
    effective_status = getattr(effective_payment, "status", None)

    if effective_status == "succeeded":
        logger.info("Платёж успешно завершён: %s", payment_id)

        # Атомарный захват: повторное уведомление YooKassa (ретрай или гонка)
        # не должно продлить подписку/сгенерировать gift-код второй раз.
        claimed = await _payments.claim_payment_processing(payment_id)
        if not claimed:
            logger.info("Платёж %s уже обработан или обрабатывается. Пропуск.", payment_id)
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
            processed_ok = True

            if is_gift:
                # 🎁 Генерация подарочного кода
                gift_code = generate_gift_code()
                escape_gift_code = escape_markdown_v2(gift_code)
                await _promo.create_gift_promo(gift_code, days_to_extend, telegram_id)
                # Увеличиваем счётчик
                try:
                    await _users.increment_gifted_subscriptions(telegram_id)
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
                    user = await _users.get_user_by_id(telegram_id)
                    if user and user["referrer_tag"]:
                        applied = await _users.award_referral(user["referrer_tag"], telegram_id)
                        if applied:
                            logger.info(f"[Referral] Зачислен реферал: @{user['referrer_tag']} от {telegram_id}")
                        else:
                            logger.info(f"[Referral] Уже начислен: {telegram_id}")
                    else:
                        logger.info(f"[Referral] Не начислен: {telegram_id}")
                except Exception as e:
                    logger.exception(f"[Referral] Ошибка: {e}")

                if isinstance(result, str) and result.startswith("❌"):
                    processed_ok = False
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

            # ✅ Обновляем статус. При ошибке начисления пишем processing_error,
            # а не succeeded: ретрай YooKassa сможет захватить платёж повторно
            # и допродлить подписку, когда панель снова заработает.
            await _payments.update_payment_status(
                payment_id,
                "succeeded" if processed_ok else "processing_error",
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
            await _payments.update_payment_status(payment_id, "processing_error")
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

from aiohttp import web
from yookassa.domain.notification import WebhookNotification
import logging
import json
from data import db_utils
import os
from bot import bot
from handlers.utils import escape_markdown_v2
from app.services.remnawave.vpn_service import extend_subscription_by_telegram_id
from data.db_utils import get_payment_status, update_payment_status
from data.db_utils import generate_gift_code
from payments.yookassa_client import fetch_payment

ADMIN_ID = int((os.getenv("ADMIN_IDS") or "").split(",")[0].strip() or "0")
logger = logging.getLogger(__name__)

async def yookassa_webhook_handler(request: web.Request):
    logger.info("Получен запрос вебхука от Yookassa.")
    try:
        payload = await request.json()
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
    payment_id = payment.id                 # Идентификатор платежа в YooKassa

    payment_api = None
    try:
        payment_api = fetch_payment(payment_id)
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
        print(f"Платеж успешно завершён: {payment_id}")

        if get_payment_status(payment_id) == "succeeded":
            logger.info("Платёж %s уже обработан. Пропуск.", payment_id)
            return web.json_response({"status": "ok"}, status=200)

        # Считываем данные из metadata
        metadata = (getattr(effective_payment, "metadata", None) or {}) if effective_payment else {}
        telegram_id = metadata.get("telegram_id")
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

            if is_gift:
                # 🎁 Генерация подарочного кода
                gift_code = generate_gift_code()
                escape_gift_code = escape_markdown_v2(gift_code)
                db_utils.create_gift_promo(gift_code, days_to_extend, creator_id=telegram_id)
                # Увеличиваем счётчик
                try:
                    db_utils.increment_gifted_subscriptions(telegram_id)
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
                # 📦 Продлеваем подписку
                result = extend_subscription_by_telegram_id(telegram_id, days_to_extend)
                logger.info("Результат продления подписки: %s", result)

                # ✅ Проверка на реферала
                try:
                    user = db_utils.get_user_by_id(telegram_id)
                    if user and user["referrer_tag"]:
                        applied = db_utils.award_referral(user["referrer_tag"], telegram_id)
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
            update_payment_status(payment_id, "succeeded")

            # 🔔 Уведомления
            try:
                await bot.send_message(telegram_id, user_message, parse_mode="MarkdownV2")
                logger.info("Сообщение пользователю отправлено")
            except Exception as e:
                logger.error("Ошибка отправки сообщения пользователю: %s", e)

            if ADMIN_ID:
                try:
                    await bot.send_message(ADMIN_ID, group_message, parse_mode="MarkdownV2")
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

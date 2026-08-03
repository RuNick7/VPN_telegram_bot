import asyncio
import logging

from aiohttp import web
from yookassa.domain.notification import WebhookNotification

from app.services.remnawave.vpn_service import extend_subscription, extend_subscription_for_row
from bot import bot
from tgvpn_shared.db import (
    LteRepository,
    PaymentRepository,
    PromoRepository,
    UserRepository,
    generate_gift_code,
)
from tgvpn_shared.settings import get_settings
from handlers.utils import escape_markdown_v2
from payments.yookassa_client import fetch_payment

ADMIN_ID = get_settings().primary_admin_id
logger = logging.getLogger(__name__)

_users = UserRepository()
_payments = PaymentRepository()
_promo = PromoRepository()
_lte = LteRepository()

# Жёсткие потолки на блокирующие сетевые вызовы, чтобы зависший
# upstream (YooKassa/Remnawave) никогда не клал event loop надолго.
YOOKASSA_FETCH_TIMEOUT_SECONDS = 15.0
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0
REQUEST_BODY_TIMEOUT_SECONDS = 10.0


async def _resolve_payer(metadata: dict) -> dict | None:
    """
    Which of our users this payment belongs to.

    Prefers our own `user_id`. That is the only identifier a website account
    with no Telegram has, and it is the one that survives an account merge --
    `get_user_by_uuid` follows `merged_into`, so a payment started before a
    merge still credits the surviving account rather than a dead row.

    Falls back to `telegram_id` for payments created before the rework and
    still in flight at YooKassa, and for anything the bot creates today.

    Metadata is read only from a *verified* fetch; see the caller.
    """
    user_id = (metadata.get("user_id") or "").strip() if metadata.get("user_id") else None
    if user_id:
        row = await _users.get_user_by_uuid(user_id)
        if row is not None:
            return dict(row)
        logger.warning("В metadata указан неизвестный user_id=%s", user_id)

    raw = metadata.get("telegram_id")
    try:
        telegram_id = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if telegram_id is None:
        return None

    row = await _users.get_user_by_id(telegram_id)
    # A payer with no row at all is still creditable: the subscription path
    # creates the row it needs. Report the ID rather than nothing.
    return dict(row) if row is not None else {"id": None, "telegram_id": telegram_id}


def _payer_label(payer: dict | None) -> str:
    """How to name a payer in a log line, whichever identity they have."""
    if not payer:
        return "?"
    return str(payer.get("telegram_id") or payer.get("id") or "?")


# Everything below picks the identity the payer actually has. A Telegram user
# goes through the telegram_id-keyed path the bot has always used; a website
# account has no Telegram ID and is addressed by our own `id`. Before this
# split existed the website case was charged and never credited.


async def _credit_traffic(payer: dict, bytes_added: int) -> int | None:
    if payer.get("telegram_id"):
        return await _lte.credit_balance(int(payer["telegram_id"]), bytes_added)
    if payer.get("id"):
        return await _lte.credit_balance_by_user_id(str(payer["id"]), bytes_added)
    return None


async def _increment_gifted(payer: dict) -> None:
    if payer.get("telegram_id"):
        await _users.increment_gifted_subscriptions(int(payer["telegram_id"]))
    elif payer.get("id"):
        await _users.increment_gifted_subscriptions_by_user_id(str(payer["id"]))


async def _extend_for_payer(payer: dict, days: int) -> str:
    if payer.get("telegram_id"):
        return await extend_subscription(int(payer["telegram_id"]), days)
    if payer.get("id"):
        return await extend_subscription_for_row(payer, days)
    return "❌ Не удалось определить пользователя."


async def _award_referral_for_payer(payer: dict) -> None:
    """
    Credit whoever invited this payer, at most once ever.

    Re-read rather than trusting the payer dict: it was assembled before the
    extension ran, and `referrer_tag` may have been set in between.
    """
    telegram_id = payer.get("telegram_id")
    user_id = payer.get("id")

    row = None
    if telegram_id:
        row = await _users.get_user_by_id(int(telegram_id))
    elif user_id:
        row = await _users.get_user_by_uuid(str(user_id))
    if row is None:
        logger.info("[Referral] Не начислен: пользователь %s не найден", _payer_label(payer))
        return

    tag = row["referrer_tag"]
    if not tag:
        logger.info("[Referral] Не начислен: пригласивший не указан (%s)", _payer_label(payer))
        return

    if telegram_id:
        applied = await _users.award_referral(tag, int(telegram_id))
    else:
        applied = await _users.award_referral_by_user_id(tag, str(row["id"]))

    logger.info(
        "[Referral] %s: @%s от %s",
        "Зачислен" if applied else "Уже начислен", tag, _payer_label(payer),
    )


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

        # Who to credit. `user_id` is our own identifier and is preferred:
        # it is the only one a website account without Telegram has, and it
        # survives an account merge because the lookup follows `merged_into`.
        # `telegram_id` is the fallback for payments created before the
        # identity rework and still in flight at YooKassa.
        payer = await _resolve_payer(metadata)
        telegram_id = payer["telegram_id"] if payer else None
        if payer is None:
            logger.error("Платёж %s: не удалось определить пользователя, metadata=%s",
                         payment_id, metadata)
        days_to_extend = metadata.get("days_to_extend", 30)
        is_gift_raw = metadata.get("is_gift", False)

        # A traffic purchase credits gigabytes and must not touch the
        # subscription date. Read from the *verified* metadata, same as
        # everything else here.
        try:
            lte_gb = int(metadata.get("lte_gb") or 0)
        except (TypeError, ValueError):
            logger.warning("Некорректный lte_gb=%s, считаем 0", metadata.get("lte_gb"))
            lte_gb = 0
        is_lte_purchase = lte_gb > 0

        try:
            days_to_extend = int(days_to_extend)
        except (TypeError, ValueError):
            logger.warning("Некорректный days_to_extend=%s, используем 30", days_to_extend)
            days_to_extend = 30

        # A traffic purchase legitimately sends 0 days; only fall back to 30
        # for subscription payments, where 0 means the value was lost.
        if days_to_extend <= 0 and not is_lte_purchase:
            logger.warning("days_to_extend=%s <= 0, используем 30", days_to_extend)
            days_to_extend = 30

        if isinstance(is_gift_raw, bool):
            is_gift = is_gift_raw
        else:
            is_gift = str(is_gift_raw).strip().lower() in {"true", "1", "yes", "y"}

        logger.info("Платёж успешен. Пользователь: %s / tg=%s, дней: %s",
                    (payer or {}).get("id"), telegram_id, days_to_extend)

        # Record whose payment this is and what it was for, from the *verified*
        # metadata. Only these columns -- the status stays where the claim
        # above put it. A payment created in the bot had no row until the
        # webhook wrote one, so without this a bot purchase that failed to
        # credit was an id and nothing else.
        if payer is not None:
            purpose = "gift" if is_gift else ("traffic" if is_lte_purchase else "subscription")
            try:
                await _payments.record_intent(
                    payment_id, str(payer["id"]) if payer.get("id") else None,
                    purpose, days_to_extend,
                )
            except Exception as exc:
                # Bookkeeping for a screen, never a reason to fail a payment.
                logger.warning("Не удалось записать назначение платежа %s: %s", payment_id, exc)

        # Branch on the payer, not on telegram_id. Gating on the Telegram ID
        # meant a website account -- which has none -- was charged, marked
        # processing_error and never credited, with no alert anywhere.
        if payer is not None:
            result = ""
            user_message = ""
            group_message = ""
            processed_ok = True

            if is_lte_purchase:
                # 📶 Начисляем купленный трафик. Additive by construction, so a
                # concurrent monitor pass spending the balance can't erase it.
                try:
                    new_balance = await _credit_traffic(payer, lte_gb * 1024**3)
                    if new_balance is None:
                        raise RuntimeError(f"пользователь {_payer_label(payer)} не найден в БД")
                    result = f"📶 Начислено {lte_gb} ГБ"
                    logger.info(
                        "[LTE] Начислено %s ГБ пользователю %s, баланс: %.2f ГБ",
                        lte_gb, _payer_label(payer), new_balance / 1024**3,
                    )
                    user_message = (
                        f"✅ Платёж успешно завершён\\!\n"
                        f"Начислено *{lte_gb} ГБ* трафика белых списков\\.\n\n"
                        f"Всего куплено: *{new_balance / 1024**3:.2f} ГБ*"
                    )
                    group_message = (
                        f"📶 Куплен трафик белых списков\n"
                        f"Пользователь: {telegram_id}\n"
                        f"Пакет: {lte_gb} ГБ"
                    )
                except Exception as exc:
                    # Mirrors the subscription-failure path: mark the payment
                    # as processing_error so a YooKassa retry can credit it.
                    processed_ok = False
                    logger.error("[LTE] Не удалось начислить %s ГБ для %s: %s",
                                 lte_gb, _payer_label(payer), exc)
                    result = f"❌ Ошибка начисления трафика: {exc}"
                    user_message = (
                        "⚠️ Платёж прошёл, но при начислении трафика возникла ошибка.\n"
                        "Мы уже занимаемся этим вопросом."
                    )
                    group_message = (
                        f"⚠️ Ошибка начисления трафика\n"
                        f"Пользователь: {telegram_id}\n"
                        f"Пакет: {lte_gb} ГБ\n"
                        f"Текст: {exc}"
                    )

            elif is_gift:
                # 🎁 Генерация подарочного кода
                gift_code = generate_gift_code()
                escape_gift_code = escape_markdown_v2(gift_code)
                # Both handles. `creator_id` is a Telegram ID and support reads
                # it; `creator_user_id` is the one that has to be there, because
                # it is how the buyer's own gifts are found. A gift bought on
                # the website used to record neither -- so the code was
                # delivered as a Telegram message the buyer could not receive,
                # and existed nowhere they could reach it.
                await _promo.create_gift_promo(
                    gift_code,
                    days_to_extend,
                    telegram_id,
                    creator_user_id=str(payer["id"]) if payer.get("id") else None,
                )
                try:
                    await _increment_gifted(payer)
                    logger.info("[GIFT] %s подарил ещё одну подписку.", _payer_label(payer))
                except Exception as e:
                    logger.error("[GIFT] Не удалось обновить gifted_subscriptions для %s: %s",
                                 _payer_label(payer), e)

                # Two ways to hand the gift over, because the recipient may
                # not be a Telegram user at all. The code is the old path and
                # still works everywhere; the link is for someone who will
                # redeem it on the website. Both redeem the *same* code, so it
                # can only be used once whichever route is taken.
                gift_link = get_settings().gift_link(gift_code)

                result = f"🎁 Промокод для подарка: `{escape_gift_code}`"
                user_message = (
                    f"✅ Платёж успешно завершен\\!\n"
                    f"Вы приобрели *подарочную подписку* на *{days_to_extend}* дней\\.\n\n"
                    f"Передайте другу этот код: `{escape_gift_code}`"
                )
                if gift_link:
                    user_message += (
                        "\n\nИли отправьте ссылку — по ней подарок можно "
                        "активировать без Telegram:\n"
                        f"{escape_markdown_v2(gift_link)}"
                    )
                group_message = (
                    f"🎁 Подарок оформлен\\!\n"
                    f"Пользователь: {telegram_id}\n"
                    f"Срок: {days_to_extend} дней\n"
                    f"Код: {escape_gift_code}"
                )
            else:
                # 📦 Продлеваем подписку. Жёсткий таймаут, чтобы зависший
                # Remnawave не держал обработку вебхука бесконечно.
                try:
                    result = await asyncio.wait_for(
                        _extend_for_payer(payer, days_to_extend),
                        timeout=REMNAWAVE_EXTEND_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    result = (
                        f"❌ Таймаут продления подписки (>{REMNAWAVE_EXTEND_TIMEOUT_SECONDS}s)"
                    )
                    logger.error("extend_subscription timeout for %s", _payer_label(payer))
                logger.info("Результат продления подписки: %s", result)

                # ✅ Реферал начисляется по факту оплаты, а не по факту
                # указания пригласившего -- иначе лестницу скидок можно было
                # бы фармить бесплатно.
                try:
                    await _award_referral_for_payer(payer)
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

            # 🔔 Уведомления. Пользователю пишем только если у него вообще
            # есть Telegram: у аккаунта с сайта его нет, и результат он видит
            # на самой странице через GET /api/payments/{id}.
            if telegram_id:
                try:
                    await _send_markdown_or_plain(telegram_id, user_message)
                    logger.info("Сообщение пользователю отправлено")
                except Exception as e:
                    logger.error("Ошибка отправки сообщения пользователю: %s", e)
            else:
                logger.info("Пользователь %s без Telegram — уведомление не отправляем",
                            _payer_label(payer))

            if ADMIN_ID:
                try:
                    await _send_markdown_or_plain(ADMIN_ID, group_message)
                    logger.info("Сообщение админу отправлено")
                except Exception as e:
                    logger.error("Ошибка отправки сообщения админу: %s", e)
            else:
                logger.warning("ADMIN_IDS не задан, уведомление админу не отправлено")
        else:
            # Money taken and nobody to credit. This must never be quiet:
            # it needs a human, and YooKassa retries will not fix it.
            logger.error("Платёж %s: пользователь не определён, metadata=%s", payment_id, metadata)
            await _payments.update_payment_status(payment_id, "processing_error")
            if ADMIN_ID:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🚨 Платёж {payment_id} прошёл, но пользователь не определён.\n"
                        f"metadata: {metadata}",
                    )
                except Exception as send_err:
                    logger.error("Ошибка отправки админу: %s", send_err)
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

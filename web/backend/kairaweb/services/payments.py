"""Payment service that talks to YooKassa via the user_bot client directly."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Any

from kairaweb.core.settings import ensure_user_bot_on_path, get_settings

ensure_user_bot_on_path()

from app.services.remnawave import vpn_service  # noqa: E402  (user_bot)
from data import db_utils  # noqa: E402
from handlers.utils import get_subscription_price  # noqa: E402  (user_bot)
from handlers.payments import LTE_GB_PRICES  # noqa: E402  (user_bot)
from payments.yookassa_client import create_payment, fetch_payment  # noqa: E402  (user_bot)


logger = logging.getLogger(__name__)

YOOKASSA_CALL_TIMEOUT_SECONDS = 15.0
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0


GIFT_TARIFFS: dict[int, dict[str, int]] = {
    1: {"price": 89, "days": 30},
    3: {"price": 249, "days": 90},
    6: {"price": 479, "days": 180},
    12: {"price": 899, "days": 365},
}


async def _create_payment_async(**kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(create_payment, **kwargs),
        timeout=YOOKASSA_CALL_TIMEOUT_SECONDS,
    )


async def _fetch_payment_async(payment_id: str):
    return await asyncio.wait_for(
        asyncio.to_thread(fetch_payment, payment_id),
        timeout=YOOKASSA_CALL_TIMEOUT_SECONDS,
    )


async def create_subscription_payment(
    *,
    telegram_id: int,
    months: int,
    return_url: str,
) -> dict[str, Any]:
    if months not in (1, 3, 6, 12):
        raise ValueError("Unsupported months value")
    user_row = await asyncio.to_thread(db_utils.get_user_by_id, telegram_id)
    referred_people = int(user_row["referred_people"]) if user_row else 0
    amount = get_subscription_price(months, referred_people)
    days_to_extend = months * 30
    description = f"Оплата подписки на {months} мес."
    payment = await _create_payment_async(
        amount=amount,
        description=description,
        return_url=return_url,
        telegram_id=int(telegram_id),
        days_to_extend=days_to_extend,
    )
    payment_id = str(payment.id)
    await asyncio.to_thread(db_utils.update_payment_status, payment_id, str(payment.status))
    return {
        "payment_id": payment_id,
        "status": str(payment.status),
        "confirmation_url": str(payment.confirmation.confirmation_url),
        "amount": float(amount),
        "currency": "RUB",
        "days_to_extend": days_to_extend,
        "kind": "subscription",
        "months": months,
    }


async def create_lte_payment(
    *,
    telegram_id: int,
    gb_amount: int,
    return_url: str,
) -> dict[str, Any]:
    amount = LTE_GB_PRICES.get(int(gb_amount))
    if amount is None:
        raise ValueError("Unknown LTE package")
    description = f"Покупка LTE трафика: {gb_amount} ГБ"
    payment = await _create_payment_async(
        amount=amount,
        description=description,
        return_url=return_url,
        telegram_id=int(telegram_id),
        days_to_extend=0,
        metadata_extra={
            "purchase_type": "lte_gb",
            "lte_gb": int(gb_amount),
        },
    )
    payment_id = str(payment.id)
    await asyncio.to_thread(db_utils.update_payment_status, payment_id, str(payment.status))
    return {
        "payment_id": payment_id,
        "status": str(payment.status),
        "confirmation_url": str(payment.confirmation.confirmation_url),
        "amount": float(amount),
        "currency": "RUB",
        "kind": "lte_gb",
        "lte_gb": int(gb_amount),
    }


async def create_gift_payment(
    *,
    telegram_id: int,
    months: int,
    return_url: str,
) -> dict[str, Any]:
    plan = GIFT_TARIFFS.get(int(months))
    if plan is None:
        raise ValueError("Unknown gift plan")
    description = f"Подарочная подписка на {months} мес."
    payment = await _create_payment_async(
        amount=plan["price"],
        description=description,
        return_url=return_url,
        telegram_id=int(telegram_id),
        days_to_extend=plan["days"],
        is_gift=True,
    )
    payment_id = str(payment.id)
    await asyncio.to_thread(db_utils.update_payment_status, payment_id, str(payment.status))
    return {
        "payment_id": payment_id,
        "status": str(payment.status),
        "confirmation_url": str(payment.confirmation.confirmation_url),
        "amount": float(plan["price"]),
        "currency": "RUB",
        "kind": "gift",
        "months": int(months),
        "days_to_extend": plan["days"],
    }


async def fetch_payment_snapshot(payment_id: str) -> dict[str, Any]:
    local_status = await asyncio.to_thread(db_utils.get_payment_status, payment_id)
    payment = await _fetch_payment_async(payment_id)
    metadata = getattr(payment, "metadata", None) or {}
    confirmation = getattr(payment, "confirmation", None)
    confirmation_url = getattr(confirmation, "confirmation_url", None) if confirmation else None
    return {
        "payment_id": payment_id,
        "status": str(getattr(payment, "status", "") or ""),
        "local_status": str(local_status or ""),
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        "confirmation_url": confirmation_url,
    }


async def process_webhook_success(payment_id: str) -> dict[str, Any]:
    if (await asyncio.to_thread(db_utils.get_payment_status, payment_id)) == "succeeded":
        return {"ok": True, "idempotent": True, "status": "succeeded"}

    payment = await _fetch_payment_async(payment_id)
    payment_status = str(getattr(payment, "status", "") or "")
    if payment_status != "succeeded":
        await asyncio.to_thread(
            db_utils.update_payment_status, payment_id, payment_status or "unknown"
        )
        return {"ok": True, "idempotent": False, "status": payment_status or "unknown"}

    metadata = getattr(payment, "metadata", None) or {}
    telegram_id_raw = metadata.get("telegram_id")
    days_to_extend_raw = metadata.get("days_to_extend", 30)
    is_gift_raw = metadata.get("is_gift", False)
    purchase_type = str(metadata.get("purchase_type") or "").strip().lower()
    lte_gb_raw = metadata.get("lte_gb", 0)

    if telegram_id_raw is None:
        raise ValueError("Missing telegram_id in payment metadata")
    try:
        telegram_id = int(telegram_id_raw)
        days_to_extend = int(days_to_extend_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid payment metadata values") from exc

    if days_to_extend <= 0 and purchase_type != "lte_gb":
        days_to_extend = 30

    is_gift = (
        is_gift_raw
        if isinstance(is_gift_raw, bool)
        else str(is_gift_raw).strip().lower() in {"true", "1", "yes", "y"}
    )

    if purchase_type == "lte_gb":
        try:
            lte_gb = int(lte_gb_raw)
        except (TypeError, ValueError):
            lte_gb = 0
        if lte_gb <= 0:
            await asyncio.to_thread(
                db_utils.update_payment_status, payment_id, "processing_error"
            )
            raise ValueError("Invalid lte_gb metadata")
        await asyncio.to_thread(db_utils.add_lte_paid_gb, telegram_id, lte_gb)
        await asyncio.to_thread(db_utils.update_payment_status, payment_id, "succeeded")
        return {
            "ok": True,
            "idempotent": False,
            "status": "succeeded",
            "telegram_id": telegram_id,
            "lte_gb": lte_gb,
        }

    if is_gift:
        gift_code = await asyncio.to_thread(db_utils.generate_gift_code)
        await asyncio.to_thread(
            db_utils.create_gift_promo, gift_code, days_to_extend, telegram_id
        )
        try:
            await asyncio.to_thread(db_utils.increment_gifted_subscriptions, telegram_id)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to increment gifted_subscriptions: %s", exc)
        await asyncio.to_thread(db_utils.update_payment_status, payment_id, "succeeded")
        return {
            "ok": True,
            "idempotent": False,
            "status": "succeeded",
            "telegram_id": telegram_id,
            "days_to_extend": days_to_extend,
            "gift_code": gift_code,
        }

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                vpn_service.extend_subscription_by_telegram_id,
                telegram_id,
                days_to_extend,
            ),
            timeout=REMNAWAVE_EXTEND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        await asyncio.to_thread(db_utils.update_payment_status, payment_id, "processing_error")
        raise ValueError("Remnawave extend timeout") from exc

    if isinstance(result, str) and result.startswith("❌"):
        await asyncio.to_thread(db_utils.update_payment_status, payment_id, "processing_error")
        raise ValueError(result)

    try:
        user = await asyncio.to_thread(db_utils.get_user_by_id, telegram_id)
        if user and user["referrer_tag"]:
            await asyncio.to_thread(
                db_utils.award_referral, user["referrer_tag"], telegram_id
            )
    except Exception as exc:  # pragma: no cover
        logger.exception("Referral award failed: %s", exc)

    await asyncio.to_thread(db_utils.update_payment_status, payment_id, "succeeded")
    return {
        "ok": True,
        "idempotent": False,
        "status": "succeeded",
        "telegram_id": telegram_id,
        "days_to_extend": days_to_extend,
    }


def is_allowed_webhook_source(request_ip: str | None) -> bool:
    settings = get_settings()
    allowed = settings.yookassa_webhook_allowed_cidrs.strip()
    if not allowed:
        return True
    if not request_ip:
        return False
    try:
        ip_addr = ipaddress.ip_address(request_ip)
    except ValueError:
        return False
    cidrs = [c.strip() for c in allowed.split(",") if c.strip()]
    if not cidrs:
        return True
    for cidr in cidrs:
        try:
            if ip_addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            logger.warning("Invalid CIDR in YOOKASSA_WEBHOOK_ALLOWED_CIDRS: %s", cidr)
    return False


def is_valid_webhook_secret(header_secret: str | None) -> bool:
    expected = get_settings().yookassa_webhook_secret
    if not expected:
        return True
    return bool(header_secret) and header_secret == expected

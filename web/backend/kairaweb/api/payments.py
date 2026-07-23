"""Payment status endpoint and YooKassa webhook."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kairaweb.api.deps import current_user
from kairaweb.core.security import get_client_ip
from kairaweb.services.payments import (
    fetch_payment_snapshot,
    is_allowed_webhook_source,
    is_valid_webhook_secret,
    process_webhook_success,
)


router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.get("/{payment_id}")
async def get_payment(payment_id: str, request: Request, user=current_user) -> dict[str, Any]:
    try:
        payment = await fetch_payment_snapshot(payment_id)
    except Exception as exc:
        logger.exception("payment_fetch_failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

    metadata = payment.get("metadata") or {}
    meta_telegram_id = metadata.get("telegram_id")
    if meta_telegram_id is not None and str(meta_telegram_id) != str(user["telegram_id"]):
        raise HTTPException(status_code=403, detail="Forbidden for this payment.")
    return payment


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request) -> dict[str, Any]:
    request_ip = get_client_ip(request)
    if not is_allowed_webhook_source(request_ip):
        logger.warning("webhook_rejected_source source_ip=%s", request_ip)
        raise HTTPException(status_code=401, detail="Webhook source is not allowed.")

    header_secret = request.headers.get("x-kaira-webhook-secret")
    if not is_valid_webhook_secret(header_secret):
        logger.warning("webhook_rejected_secret source_ip=%s", request_ip)
        raise HTTPException(status_code=401, detail="Webhook secret is invalid.")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("webhook_invalid_json source_ip=%s", request_ip)
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    event = (payload or {}).get("event")
    payment_obj = (payload or {}).get("object") or {}
    payment_id = payment_obj.get("id")
    logger.info("webhook_received event=%s payment_id=%s source_ip=%s", event, payment_id, request_ip)
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment id in payload.")

    if event != "payment.succeeded":
        return {"ok": True, "ignored": True, "event": event}

    try:
        result = await process_webhook_success(str(payment_id))
    except ValueError as exc:
        logger.error("webhook_processing_failed payment_id=%s reason=%s", payment_id, exc)
        raise HTTPException(status_code=502, detail="Webhook processing failed.") from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("webhook_processing_failed payment_id=%s reason=%s", payment_id, exc)
        raise HTTPException(status_code=502, detail="Webhook processing failed.") from exc

    return {
        "ok": True,
        "payment_id": str(payment_id),
        "status": result.get("status"),
        "idempotent": bool(result.get("idempotent")),
    }

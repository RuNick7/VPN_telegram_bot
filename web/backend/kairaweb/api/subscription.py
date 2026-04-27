"""Subscription endpoints: snapshot, tariffs, manual extend (creates payment)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from kairaweb.api.deps import current_user
from kairaweb.core.settings import get_settings
from kairaweb.services.instructions import build_qr_data_url
from kairaweb.services.payments import create_subscription_payment
from kairaweb.services.user_service import (
    get_subscription_snapshot,
    get_user_record,
    list_tariffs_for_user,
)


router = APIRouter(prefix="/api/subscription", tags=["subscription"])
logger = logging.getLogger(__name__)


class ExtendRequest(BaseModel):
    months: int
    return_url: str | None = None


@router.get("")
async def subscription_snapshot(request: Request, user=current_user) -> dict[str, Any]:
    telegram_id = int(user["telegram_id"])
    snapshot = await get_subscription_snapshot(telegram_id)
    snapshot["qr_data_url"] = build_qr_data_url(snapshot.get("subscription_url") or "")
    return snapshot


@router.get("/tariffs")
async def subscription_tariffs(request: Request, user=current_user) -> dict[str, Any]:
    telegram_id = int(user["telegram_id"])
    user_row = get_user_record(telegram_id) or {}
    referred = int(user_row.get("referred_people") or 0)
    return {
        "referred_people": referred,
        "tariffs": list_tariffs_for_user(referred),
    }


@router.post("/extend")
async def subscription_extend(payload: ExtendRequest, request: Request, user=current_user) -> dict[str, Any]:
    settings = get_settings()
    months = int(payload.months)
    if months not in (1, 3, 6, 12):
        raise HTTPException(status_code=400, detail="Unsupported months value.")
    return_url = (payload.return_url or settings.web_payment_return_url).strip()
    if not return_url:
        raise HTTPException(status_code=400, detail="return_url is required.")
    try:
        return await create_subscription_payment(
            telegram_id=int(user["telegram_id"]),
            months=months,
            return_url=return_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to create subscription payment: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

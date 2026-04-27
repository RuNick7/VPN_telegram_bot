"""/api/me — profile, subscription summary."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kairaweb.api.deps import current_user
from kairaweb.services.user_service import (
    get_lte_remaining_bytes,
    get_subscription_snapshot,
    get_user_record,
    referral_summary,
)


router = APIRouter(prefix="/api", tags=["me"])
logger = logging.getLogger(__name__)


@router.get("/me")
async def get_me(request: Request, user=current_user) -> dict[str, Any]:
    telegram_id = int(user["telegram_id"])
    user_row = get_user_record(telegram_id) or {}
    response: dict[str, Any] = {
        "telegram_id": telegram_id,
        "username": user.get("username") or user_row.get("telegram_tag") or None,
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "photo_url": user.get("photo_url"),
        "email": user_row.get("email") or user.get("email") or None,
        "is_telegram_linked": True,
        "subscription": None,
        "lte_remaining_bytes": 0,
        "lte_remaining_gb": 0.0,
        "referrals": referral_summary(user_row),
    }
    try:
        response["subscription"] = await get_subscription_snapshot(telegram_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("subscription_snapshot_failed telegram_id=%s: %s", telegram_id, exc)

    try:
        remaining_bytes = get_lte_remaining_bytes(telegram_id)
        response["lte_remaining_bytes"] = remaining_bytes
        response["lte_remaining_gb"] = round(max(0, remaining_bytes) / (1024 ** 3), 2)
    except Exception as exc:  # pragma: no cover
        logger.warning("lte_snapshot_failed telegram_id=%s: %s", telegram_id, exc)

    return response

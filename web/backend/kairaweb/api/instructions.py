"""Per-platform install instructions for the cabinet."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kairaweb.api.deps import current_user
from kairaweb.services.instructions import SUPPORTED_PLATFORMS, build_instructions, build_qr_data_url
from kairaweb.services.user_service import get_subscription_snapshot


router = APIRouter(prefix="/api", tags=["instructions"])
logger = logging.getLogger(__name__)


@router.get("/instructions/{platform}")
async def instructions(platform: str, request: Request, user=current_user) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail="Unsupported platform.")
    snapshot = await get_subscription_snapshot(int(user["telegram_id"]))
    sub_url = snapshot.get("subscription_url") or ""
    payload = build_instructions(platform, sub_url)
    payload["qr_data_url"] = build_qr_data_url(sub_url) if sub_url else None
    payload["subscription"] = snapshot
    return payload

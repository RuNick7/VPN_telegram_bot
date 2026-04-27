"""Web push endpoints: subscribe / unsubscribe / public VAPID key."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from kairaweb.core.settings import get_settings
from kairaweb.core.storage import (
    delete_push_subscription_by_endpoint,
    upsert_push_subscription,
)


router = APIRouter(prefix="/api/push", tags=["push"])
logger = logging.getLogger(__name__)


class PushKeys(BaseModel):
    p256dh: str = Field(..., min_length=8)
    auth: str = Field(..., min_length=4)


class PushSubscribePayload(BaseModel):
    endpoint: str = Field(..., min_length=12)
    keys: PushKeys


class PushUnsubscribePayload(BaseModel):
    endpoint: str = Field(..., min_length=12)


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict:
    """Public; safe to expose. Used by the SW to call pushManager.subscribe."""
    settings = get_settings()
    if not settings.vapid_public_key:
        raise HTTPException(status_code=503, detail="Push notifications are not configured.")
    return {"public_key": settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe(payload: PushSubscribePayload, request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("telegram_id"):
        raise HTTPException(status_code=401, detail="Unauthorized.")

    user_agent = request.headers.get("User-Agent")
    upsert_push_subscription(
        telegram_id=int(user["telegram_id"]),
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=user_agent,
    )
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(payload: PushUnsubscribePayload, request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("telegram_id"):
        raise HTTPException(status_code=401, detail="Unauthorized.")
    deleted = delete_push_subscription_by_endpoint(payload.endpoint)
    return {"ok": True, "deleted": int(deleted)}

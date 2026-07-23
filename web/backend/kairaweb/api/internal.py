"""Internal endpoints used by the user_bot to confirm web deep-link tokens
and to dispatch web-push notifications after backend events.

All routes here are protected by a shared secret (`WEB_INTERNAL_SECRET`) and
expected to be reached only via loopback (nginx blocks `/api/internal/*` from
the public internet).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from kairaweb.services.auth import confirm_telegram_link
from kairaweb.services.push_service import send_to_user, send_to_users


router = APIRouter(prefix="/api/internal", tags=["internal"])
logger = logging.getLogger(__name__)


class TelegramLinkConfirmRequest(BaseModel):
    token: str
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class PushSendRequest(BaseModel):
    telegram_id: int | None = None
    telegram_ids: list[int] | None = None
    title: str = Field(..., max_length=120)
    body: str = Field("", max_length=400)
    url: str | None = None
    tag: str | None = None
    data: dict[str, Any] | None = None


def _check_internal_secret(header_value: str | None) -> None:
    expected = (os.getenv("WEB_INTERNAL_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="Internal endpoint disabled.")
    if not header_value or header_value != expected:
        raise HTTPException(status_code=401, detail="Invalid internal secret.")


@router.post("/telegram-link/confirm")
async def confirm_telegram_link_endpoint(
    payload: TelegramLinkConfirmRequest,
    x_kaira_internal_secret: str | None = Header(default=None, alias="X-Kaira-Internal-Secret"),
) -> dict:
    _check_internal_secret(x_kaira_internal_secret)
    record = confirm_telegram_link(
        raw_token=payload.token,
        telegram_id=int(payload.telegram_id),
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Token not found or already used.")
    return {"ok": True, "telegram_id": int(payload.telegram_id)}


@router.post("/push/send")
async def push_send_endpoint(
    payload: PushSendRequest,
    x_kaira_internal_secret: str | None = Header(default=None, alias="X-Kaira-Internal-Secret"),
) -> dict:
    _check_internal_secret(x_kaira_internal_secret)
    if not payload.telegram_id and not payload.telegram_ids:
        raise HTTPException(status_code=400, detail="telegram_id or telegram_ids is required.")

    kwargs = dict(
        title=payload.title,
        body=payload.body,
        url=payload.url,
        tag=payload.tag,
        data=payload.data,
    )

    if payload.telegram_ids:
        delivered = await asyncio.to_thread(send_to_users, payload.telegram_ids, **kwargs)
    else:
        delivered = await asyncio.to_thread(send_to_user, int(payload.telegram_id), **kwargs)
    return {"ok": True, "delivered": int(delivered)}

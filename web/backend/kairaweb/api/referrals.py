"""Referrals + promo redeem endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from kairaweb.api.deps import current_user
from kairaweb.core.settings import get_settings
from kairaweb.services.referrals import (
    PromoError,
    ReferralError,
    redeem_promo,
    referral_overview,
    set_referrer,
)


router = APIRouter(prefix="/api", tags=["referrals"])
logger = logging.getLogger(__name__)


class ReferralSetRequest(BaseModel):
    referrer_tag: str


class PromoRedeemRequest(BaseModel):
    code: str


@router.get("/referrals")
async def get_referrals(request: Request, user=current_user) -> dict[str, Any]:
    settings = get_settings()
    overview = await referral_overview(int(user["telegram_id"]))
    bot_username = settings.telegram_bot_username
    if overview.get("telegram_tag") and bot_username:
        overview["share_link"] = f"https://t.me/{bot_username}?start=ref_{overview['telegram_tag']}"
    return overview


@router.post("/referrals/set")
async def set_referrer_endpoint(payload: ReferralSetRequest, request: Request, user=current_user) -> dict[str, Any]:
    try:
        return await set_referrer(int(user["telegram_id"]), payload.referrer_tag)
    except ReferralError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/promo/redeem")
async def promo_redeem(payload: PromoRedeemRequest, request: Request, user=current_user) -> dict[str, Any]:
    try:
        return await redeem_promo(int(user["telegram_id"]), payload.code)
    except PromoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

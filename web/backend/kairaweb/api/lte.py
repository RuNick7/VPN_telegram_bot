"""LTE GB packages and purchase."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from kairaweb.api.deps import current_user
from kairaweb.core.settings import ensure_user_bot_on_path, get_settings
from kairaweb.services.payments import create_lte_payment

ensure_user_bot_on_path()

from handlers.payments import LTE_GB_PRICES  # noqa: E402  (user_bot)


router = APIRouter(prefix="/api/lte", tags=["lte"])
logger = logging.getLogger(__name__)


class LtePurchaseRequest(BaseModel):
    gb: int
    return_url: str | None = None


@router.get("/packages")
async def lte_packages() -> dict[str, Any]:
    return {
        "packages": [
            {"gb": int(gb), "price": int(price)}
            for gb, price in sorted(LTE_GB_PRICES.items())
        ]
    }


@router.post("/buy")
async def lte_buy(payload: LtePurchaseRequest, request: Request, user=current_user) -> dict[str, Any]:
    settings = get_settings()
    return_url = (payload.return_url or settings.web_payment_return_url).strip()
    if not return_url:
        raise HTTPException(status_code=400, detail="return_url is required.")
    try:
        return await create_lte_payment(
            telegram_id=int(user["telegram_id"]),
            gb_amount=int(payload.gb),
            return_url=return_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("LTE buy failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

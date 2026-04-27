"""Gift subscription tariffs and purchase."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from kairaweb.api.deps import current_user
from kairaweb.core.settings import get_settings
from kairaweb.services.payments import GIFT_TARIFFS, create_gift_payment


router = APIRouter(prefix="/api/gifts", tags=["gifts"])
logger = logging.getLogger(__name__)


class GiftPurchaseRequest(BaseModel):
    months: int
    return_url: str | None = None


@router.get("/tariffs")
async def gift_tariffs() -> dict[str, Any]:
    return {
        "tariffs": [
            {"months": int(months), "price": int(plan["price"]), "days": int(plan["days"])}
            for months, plan in sorted(GIFT_TARIFFS.items())
        ],
    }


@router.post("/buy")
async def gift_buy(payload: GiftPurchaseRequest, request: Request, user=current_user) -> dict[str, Any]:
    settings = get_settings()
    return_url = (payload.return_url or settings.web_payment_return_url).strip()
    if not return_url:
        raise HTTPException(status_code=400, detail="return_url is required.")
    try:
        return await create_gift_payment(
            telegram_id=int(user["telegram_id"]),
            months=int(payload.months),
            return_url=return_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("Gift buy failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

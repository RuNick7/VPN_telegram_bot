"""User profile / subscription helpers backed by user_bot db_utils."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from kairaweb.core.settings import ensure_user_bot_on_path

ensure_user_bot_on_path()

from data import db_utils  # noqa: E402
from app.config.settings import get_remnawave_settings  # noqa: E402  (user_bot)
from app.services.remnawave import vpn_service  # noqa: E402  (user_bot)
from handlers.constants import PRICES, SECONDS_IN_DAY  # noqa: E402  (user_bot)
from handlers.utils import get_subscription_price  # noqa: E402  (user_bot)


REMNAWAVE_CALL_TIMEOUT_SECONDS = 10.0


async def _to_thread(func, *args, **kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(func, *args, **kwargs),
        timeout=REMNAWAVE_CALL_TIMEOUT_SECONDS,
    )


def get_user_record(telegram_id: int) -> dict[str, Any] | None:
    row = db_utils.get_user_by_id(int(telegram_id))
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


async def get_user_record_async(telegram_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_user_record, telegram_id)


def update_user_email(telegram_id: int, email: str) -> None:
    db_utils.update_user_email(int(telegram_id), email)


def ensure_user_record(telegram_id: int, username: str | None) -> None:
    if not db_utils.user_in_db(int(telegram_id)):
        db_utils.create_user_record(int(telegram_id), username or str(telegram_id))


def get_lte_remaining_bytes(telegram_id: int) -> int:
    settings = get_remnawave_settings()
    return int(
        db_utils.get_lte_remaining_bytes(
            int(telegram_id),
            free_gb=settings.lte_free_gb_per_30d,
        )
    )


def format_gb_from_bytes(value: int) -> float:
    return round(max(0, int(value)) / (1024 ** 3), 2)


async def get_subscription_snapshot(telegram_id: int) -> dict[str, Any]:
    """Combine local subscription_ends with Remnawave subscription URL."""
    user_row = await asyncio.to_thread(get_user_record, telegram_id)
    subscription_ends = int(
        (user_row or {}).get("subscription_ends") or 0
    )
    username = str(int(telegram_id))

    expire_at = 0
    subscription_url = ""
    panel_user_exists = False
    try:
        token = await _to_thread(vpn_service.get_token, int(telegram_id))
        expire_at = int(await _to_thread(vpn_service.get_user_expire, username, token))
        subscription_url = await _to_thread(vpn_service.get_subscription_url, username, token)
        panel_user_exists = True
    except ValueError as exc:
        if "User not found" not in str(exc):
            raise
    now_ts = int(time.time())
    return {
        "telegram_id": int(telegram_id),
        "subscription_ends": subscription_ends,
        "expire_at": expire_at,
        "is_active": subscription_ends > now_ts,
        "subscription_url": subscription_url,
        "panel_user_exists": panel_user_exists,
        "expires_iso": _iso_or_empty(subscription_ends),
        "days_left": max(0, (subscription_ends - now_ts) // SECONDS_IN_DAY) if subscription_ends else 0,
    }


def _iso_or_empty(ts: int) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def list_tariffs_for_user(referred_people: int) -> list[dict[str, Any]]:
    months_options = (1, 3, 6, 12)
    monthly_price = get_subscription_price(1, referred_people)
    tariffs: list[dict[str, Any]] = []
    for months in months_options:
        price = get_subscription_price(months, referred_people)
        full_price = monthly_price * months
        discount_percent = 0
        if months > 1 and monthly_price and price < full_price:
            discount_percent = round((1 - (price / full_price)) * 100)
        tariffs.append(
            {
                "months": months,
                "days": months * 30,
                "price": int(price),
                "monthly_equivalent": int(round(price / months)),
                "full_price": int(full_price),
                "discount_percent": int(discount_percent),
            }
        )
    return tariffs


def referral_summary(user_row: dict[str, Any] | None) -> dict[str, Any]:
    if not user_row:
        return {
            "referrer_tag": None,
            "referred_people": 0,
            "gifted_subscriptions": 0,
            "tier": 0,
        }
    referred_people = int(user_row.get("referred_people") or 0)
    return {
        "referrer_tag": user_row.get("referrer_tag") or None,
        "referred_people": referred_people,
        "gifted_subscriptions": int(user_row.get("gifted_subscriptions") or 0),
        "tier": min(referred_people, max(PRICES.keys())),
    }

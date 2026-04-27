"""Referral and promo helpers backed by user_bot db."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from kairaweb.core.settings import ensure_user_bot_on_path

ensure_user_bot_on_path()

from app.services.remnawave import vpn_service  # noqa: E402  (user_bot)
from data import db_utils  # noqa: E402
from handlers.constants import SECONDS_IN_DAY, TRIAL_DAYS  # noqa: E402  (user_bot)


logger = logging.getLogger(__name__)
REMNAWAVE_EXTEND_TIMEOUT_SECONDS = 20.0


def _row_get(row, key, default=0):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def _has_paid_before(user_row) -> bool:
    if not user_row:
        return False
    try:
        created_at = int(_row_get(user_row, "created_at", 0) or 0)
        subscription_ends = int(_row_get(user_row, "subscription_ends", 0) or 0)
    except (TypeError, ValueError):
        return False
    if created_at <= 0 or subscription_ends <= 0:
        return False
    return subscription_ends > created_at + TRIAL_DAYS * SECONDS_IN_DAY


async def referral_overview(telegram_id: int) -> dict[str, Any]:
    user = await asyncio.to_thread(db_utils.get_user_by_id, int(telegram_id))
    if user is None:
        return {
            "telegram_tag": None,
            "referrer_tag": None,
            "referred_people": 0,
            "gifted_subscriptions": 0,
            "is_referred": False,
            "share_link": None,
        }
    return {
        "telegram_tag": _row_get(user, "telegram_tag", "") or None,
        "referrer_tag": _row_get(user, "referrer_tag", "") or None,
        "referred_people": int(_row_get(user, "referred_people", 0) or 0),
        "gifted_subscriptions": int(_row_get(user, "gifted_subscriptions", 0) or 0),
        "is_referred": bool(_row_get(user, "is_referred", 0) or 0),
        "share_link": None,
    }


class ReferralError(RuntimeError):
    pass


async def set_referrer(telegram_id: int, referrer_tag: str) -> dict[str, Any]:
    tag = (referrer_tag or "").strip().lstrip("@")
    if not tag:
        raise ReferralError("Введите ник пригласившего.")

    user_row = await asyncio.to_thread(db_utils.get_user_by_id, int(telegram_id))
    if not user_row:
        raise ReferralError("Профиль ещё не создан.")
    if _row_get(user_row, "referrer_tag", "") or "":
        raise ReferralError("Вы уже указали пригласившего ранее.")

    own_tag = (_row_get(user_row, "telegram_tag", "") or "").lstrip("@")
    if own_tag and own_tag.lower() == tag.lower():
        raise ReferralError("Нельзя указать самого себя.")

    referrer_row = await asyncio.to_thread(db_utils.get_user_by_tag, tag)
    if not referrer_row:
        raise ReferralError("Пользователь с таким ником не найден.")

    await asyncio.to_thread(db_utils.set_referrer_tag, int(telegram_id), tag)
    paid_before = _has_paid_before(user_row)
    awarded = False
    if paid_before:
        awarded = await asyncio.to_thread(db_utils.award_referral, tag, int(telegram_id))

    return {
        "ok": True,
        "referrer_tag": tag,
        "awarded_now": awarded,
        "message": (
            "Реферальный бонус начислен сразу — у вас уже была оплаченная подписка."
            if awarded
            else "Бонус начислится после вашей первой оплаты."
            if paid_before
            else "Бонус начислится после вашей первой оплаты."
        ),
    }


class PromoError(RuntimeError):
    pass


async def redeem_promo(telegram_id: int, code: str) -> dict[str, Any]:
    cleaned = (code or "").strip().upper()
    if not cleaned:
        raise PromoError("Введите промокод.")
    promo = await asyncio.to_thread(db_utils.get_promo_by_code, cleaned)
    if not promo or not promo["is_active"]:
        raise PromoError("Промокод недействителен.")

    if promo["type"] == "gift":
        creator_id_raw = promo["creator_id"] if "creator_id" in promo.keys() else None
        try:
            creator_id = int(creator_id_raw) if creator_id_raw is not None else None
        except (TypeError, ValueError):
            creator_id = None
        if creator_id is not None and creator_id == int(telegram_id):
            raise PromoError("Нельзя активировать собственный подарочный промокод.")
        if await asyncio.to_thread(db_utils.has_any_usage, cleaned):
            raise PromoError("Этот подарочный промокод уже использован.")
        added_days = int(promo["value"])
        result = await _extend_subscription_async(int(telegram_id), added_days)
        if isinstance(result, str) and result.startswith("❌"):
            raise PromoError(result)
        await asyncio.to_thread(db_utils.save_promo_usage, cleaned, int(telegram_id))
        return {"ok": True, "type": "gift", "added_days": added_days, "code": cleaned}

    if await asyncio.to_thread(db_utils.has_used_promo, cleaned, int(telegram_id)):
        raise PromoError("Вы уже использовали этот промокод.")

    if promo["type"] == "days":
        added_days = int(promo["value"])
        result = await _extend_subscription_async(int(telegram_id), added_days)
        if isinstance(result, str) and result.startswith("❌"):
            raise PromoError(result)
        await asyncio.to_thread(db_utils.save_promo_usage, cleaned, int(telegram_id))
        return {"ok": True, "type": "days", "added_days": added_days, "code": cleaned}

    raise PromoError(f"Тип промокода {promo['type']} пока не поддерживается.")


async def _extend_subscription_async(telegram_id: int, days: int) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                vpn_service.extend_subscription_by_telegram_id, int(telegram_id), int(days)
            ),
            timeout=REMNAWAVE_EXTEND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return f"❌ Таймаут продления подписки (>{REMNAWAVE_EXTEND_TIMEOUT_SECONDS}s)"

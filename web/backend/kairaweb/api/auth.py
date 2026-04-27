"""Authentication endpoints: Telegram widget + deep-link, email magic link."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from kairaweb.core.security import (
    attach_session_cookie,
    clear_session_cookie,
    get_client_ip,
    issue_session_token,
    normalize_email,
    validate_telegram_widget_signature,
)
from kairaweb.core.settings import get_settings
from kairaweb.core.storage import record_rate_limit_hit
from kairaweb.services.auth import (
    AuthError,
    confirm_telegram_link,
    get_telegram_link_status,
    issue_telegram_link,
    request_magic_link_for_login,
    request_magic_link_for_signup,
    verify_magic_link,
)
from kairaweb.services.user_service import ensure_user_record, get_user_record


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class TelegramWidgetPayload(BaseModel):
    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class TelegramStartResponse(BaseModel):
    token: str
    deeplink: str
    expires_at: int
    bot_username: str | None = None


class TelegramStatusResponse(BaseModel):
    status: str
    telegram_id: int | None = None
    username: str | None = None


class EmailRequest(BaseModel):
    email: str


class EmailSignupRequest(BaseModel):
    email: str
    link_token: str = Field(..., description="Token returned by /auth/telegram/start")


class MagicLinkVerifyRequest(BaseModel):
    token: str


def _check_rate_limit(request: Request, *, bucket: str = "auth_general") -> None:
    settings = get_settings()
    ip = get_client_ip(request)
    if not record_rate_limit_hit(
        bucket=bucket,
        ip=ip,
        window_seconds=settings.auth_rate_limit_window_seconds,
        max_hits=settings.auth_rate_limit_max_requests,
    ):
        raise HTTPException(status_code=429, detail="Too many requests, please retry later.")


def _user_claims(*, telegram_id: int, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    user_row = get_user_record(int(telegram_id)) or {}
    profile = profile or {}
    return {
        "telegram_id": int(telegram_id),
        "username": profile.get("username") or user_row.get("telegram_tag") or None,
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
        "photo_url": profile.get("photo_url"),
        "email": user_row.get("email") or None,
    }


@router.post("/telegram/start", response_model=TelegramStartResponse)
async def telegram_start(request: Request) -> TelegramStartResponse:
    _check_rate_limit(request, bucket="auth_telegram_start")
    payload = issue_telegram_link()
    return TelegramStartResponse(**payload)


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(token: str, request: Request) -> Response:
    _check_rate_limit(request, bucket="auth_telegram_status")
    status_payload = get_telegram_link_status(token)
    if status_payload["status"] != "confirmed":
        return Response(
            content=TelegramStatusResponse(**status_payload).model_dump_json(),
            media_type="application/json",
        )
    response = Response(
        content=TelegramStatusResponse(**status_payload).model_dump_json(),
        media_type="application/json",
    )
    return response


@router.post("/telegram/verify-widget")
async def telegram_widget_login(payload: TelegramWidgetPayload, request: Request) -> Response:
    """Optional fallback: classic Telegram Login Widget on the same domain."""
    _check_rate_limit(request, bucket="auth_telegram_widget")
    validate_telegram_widget_signature(payload.model_dump())
    ensure_user_record(payload.id, payload.username)
    profile = {
        "username": payload.username,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "photo_url": payload.photo_url,
    }
    user_claims = _user_claims(telegram_id=payload.id, profile=profile)
    token = issue_session_token(user_claims)
    response = Response(
        content=_json({"ok": True, "user": user_claims}),
        media_type="application/json",
    )
    attach_session_cookie(response, token)
    return response


@router.post("/email/request")
async def email_request_login(payload: EmailRequest, request: Request) -> Response:
    email = normalize_email(payload.email)
    try:
        body = request_magic_link_for_login(ip=get_client_ip(request), email=email)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return Response(content=_json(body), media_type="application/json")


@router.post("/email/signup")
async def email_request_signup(payload: EmailSignupRequest, request: Request) -> Response:
    email = normalize_email(payload.email)
    status_payload = get_telegram_link_status(payload.link_token)
    if status_payload["status"] != "confirmed" or not status_payload.get("telegram_id"):
        raise HTTPException(status_code=400, detail="Telegram account is not linked yet.")
    try:
        body = request_magic_link_for_signup(
            ip=get_client_ip(request),
            telegram_id=int(status_payload["telegram_id"]),
            email=email,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return Response(content=_json(body), media_type="application/json")


@router.post("/magic-link/verify")
async def verify_magic(payload: MagicLinkVerifyRequest, request: Request) -> Response:
    _check_rate_limit(request, bucket="auth_magic_verify")
    if not payload.token.strip():
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        result = verify_magic_link(payload.token.strip())
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    user_claims = _user_claims(telegram_id=int(result["telegram_id"]))
    user_claims["email"] = result.get("email") or user_claims.get("email")
    token = issue_session_token(user_claims)
    response = Response(
        content=_json({"ok": True, "purpose": result["purpose"], "user": user_claims}),
        media_type="application/json",
    )
    attach_session_cookie(response, token)
    return response


@router.post("/logout")
async def logout() -> Response:
    response = Response(content=_json({"ok": True}), media_type="application/json")
    clear_session_cookie(response)
    return response


def _json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)

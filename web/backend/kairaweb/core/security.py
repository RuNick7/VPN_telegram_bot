"""Session/JWT utilities and request helpers."""

from __future__ import annotations

import hashlib
import hmac
import time
from email.utils import parseaddr
from typing import Any

import jwt
from fastapi import HTTPException, Request, Response

from kairaweb.core.settings import get_settings


TELEGRAM_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def normalize_email(raw_email: str) -> str:
    parsed_name, parsed_email = parseaddr((raw_email or "").strip())
    if parsed_name and "<" in raw_email and ">" in raw_email:
        parsed_email = ""
    email = parsed_email.lower().strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email.")
    return email


def issue_session_token(user_claims: dict[str, Any]) -> str:
    settings = get_settings()
    now = int(time.time())
    exp = now + settings.jwt_expires_minutes * 60
    claims = {
        "sub": str(user_claims["telegram_id"]),
        "telegram_id": int(user_claims["telegram_id"]),
        "username": user_claims.get("username"),
        "first_name": user_claims.get("first_name"),
        "last_name": user_claims.get("last_name"),
        "photo_url": user_claims.get("photo_url"),
        "email": user_claims.get("email"),
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc


def attach_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    samesite = settings.session_cookie_samesite
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=samesite,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )


def validate_telegram_widget_signature(payload: dict[str, Any]) -> None:
    settings = get_settings()
    bot_token = settings.telegram_bot_token
    if not bot_token:
        raise HTTPException(status_code=401, detail="Telegram auth is not configured.")

    payload_dict = {k: v for k, v in payload.items() if v is not None and k != "hash"}
    data_check_string = "\n".join(f"{k}={payload_dict[k]}" for k in sorted(payload_dict))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(payload.get("hash", ""))):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature.")
    if int(time.time()) - int(payload.get("auth_date") or 0) > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram auth data is too old.")


def get_user_from_request(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return user

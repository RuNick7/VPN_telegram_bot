"""Authentication helpers: Telegram deep-link + email magic link."""

from __future__ import annotations

import logging
from typing import Any

from kairaweb.core.settings import get_settings
from kairaweb.core.storage import (
    cleanup_expired_magic_links,
    cleanup_expired_telegram_links,
    create_magic_link,
    create_pending_telegram_link,
    get_telegram_link_by_token,
    confirm_telegram_link_by_token,
    consume_magic_link,
    record_rate_limit_hit,
)
from kairaweb.email_sender import get_email_sender
from kairaweb.services.user_service import (
    ensure_user_record,
    get_user_record,
    update_user_email,
)

logger = logging.getLogger(__name__)

email_sender = get_email_sender()


def issue_telegram_link(*, app_base_url: str | None = None) -> dict[str, Any]:
    cleanup_expired_telegram_links()
    settings = get_settings()
    raw_token, expires_at = create_pending_telegram_link(
        ttl_seconds=settings.tg_link_ttl_minutes * 60,
    )
    bot_username = settings.telegram_bot_username
    deeplink = (
        f"https://t.me/{bot_username}?start=web_{raw_token}"
        if bot_username
        else f"tg://resolve?domain={bot_username}&start=web_{raw_token}"
    )
    return {
        "token": raw_token,
        "deeplink": deeplink,
        "expires_at": expires_at,
        "bot_username": bot_username or None,
    }


def get_telegram_link_status(raw_token: str) -> dict[str, Any]:
    cleanup_expired_telegram_links()
    record = get_telegram_link_by_token(raw_token)
    if not record:
        return {"status": "expired", "telegram_id": None}
    if record["status"] == "confirmed" and record.get("telegram_id"):
        return {
            "status": "confirmed",
            "telegram_id": int(record["telegram_id"]),
            "username": record.get("telegram_username") or None,
            "first_name": record.get("telegram_first_name") or None,
            "last_name": record.get("telegram_last_name") or None,
        }
    return {"status": "pending", "telegram_id": None}


def confirm_telegram_link(
    *,
    raw_token: str,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict[str, Any] | None:
    cleanup_expired_telegram_links()
    ensure_user_record(int(telegram_id), username)
    return confirm_telegram_link_by_token(
        raw_token,
        telegram_id=int(telegram_id),
        username=username,
        first_name=first_name,
        last_name=last_name,
    )


class AuthError(Exception):
    """Wraps a known auth failure to expose user-friendly errors."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def request_magic_link_for_login(*, ip: str, email: str) -> dict[str, Any]:
    settings = get_settings()
    cleanup_expired_magic_links()
    if not record_rate_limit_hit(
        bucket="auth_magic_request",
        ip=ip,
        window_seconds=settings.auth_rate_limit_window_seconds,
        max_hits=settings.auth_rate_limit_max_requests,
    ):
        raise AuthError("Слишком много запросов. Попробуйте позже.", status=429)

    record = _find_user_by_email(email)
    body: dict[str, Any] = {
        "ok": True,
        "message": "Если этот email связан с аккаунтом — мы отправили ссылку для входа.",
        "expires_in_seconds": settings.magic_link_ttl_minutes * 60,
    }
    if not record:
        return body

    raw_token, expires_at = create_magic_link(
        purpose="login_magic",
        telegram_id=int(record["telegram_id"]),
        email=email,
        ttl_seconds=settings.magic_link_ttl_minutes * 60,
    )
    _send_magic_link_email(email=email, raw_token=raw_token, purpose="login_magic")
    body["expires_in_seconds"] = max(0, expires_at - _now_ts())
    if settings.email_sender_mode == "mock":
        body["dev_magic_link_token"] = raw_token
    return body


def request_magic_link_for_signup(
    *,
    ip: str,
    telegram_id: int,
    email: str,
) -> dict[str, Any]:
    """Confirm an email for a freshly-linked Telegram account."""
    settings = get_settings()
    cleanup_expired_magic_links()
    if not record_rate_limit_hit(
        bucket="auth_signup_email",
        ip=ip,
        window_seconds=settings.auth_rate_limit_window_seconds,
        max_hits=settings.auth_rate_limit_max_requests,
    ):
        raise AuthError("Слишком много запросов. Попробуйте позже.", status=429)

    existing = _find_user_by_email(email)
    if existing and int(existing["telegram_id"]) != int(telegram_id):
        raise AuthError("Этот email уже привязан к другому аккаунту.", status=409)

    raw_token, expires_at = create_magic_link(
        purpose="link_email",
        telegram_id=int(telegram_id),
        email=email,
        ttl_seconds=settings.magic_link_ttl_minutes * 60,
    )
    _send_magic_link_email(email=email, raw_token=raw_token, purpose="link_email")
    body: dict[str, Any] = {
        "ok": True,
        "message": "Мы отправили ссылку подтверждения на email.",
        "expires_in_seconds": max(0, expires_at - _now_ts()),
    }
    if settings.email_sender_mode == "mock":
        body["dev_magic_link_token"] = raw_token
    return body


def verify_magic_link(raw_token: str) -> dict[str, Any]:
    cleanup_expired_magic_links()
    record = consume_magic_link(raw_token)
    if not record:
        raise AuthError("Ссылка недействительна или уже использована.", status=401)

    telegram_id = int(record["telegram_id"])
    email = str(record["email"])
    purpose = str(record["purpose"])

    if purpose == "link_email":
        existing = _find_user_by_email(email)
        if existing and int(existing["telegram_id"]) != telegram_id:
            raise AuthError("Email уже привязан к другому аккаунту.", status=409)
        update_user_email(telegram_id, email)

    user_row = get_user_record(telegram_id) or {}
    return {
        "purpose": purpose,
        "telegram_id": telegram_id,
        "email": email,
        "username": user_row.get("telegram_tag") or "",
    }


def _find_user_by_email(email: str) -> dict[str, Any] | None:
    """Look up a subscription row by stored email."""
    from kairaweb.core.storage import web_db  # local import to avoid circular

    with web_db() as conn:
        import sqlite3

        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT telegram_id, email, telegram_tag FROM subscription WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def _send_magic_link_email(*, email: str, raw_token: str, purpose: str) -> None:
    settings = get_settings()
    verify_url = f"{settings.app_base_url}/auth/magic?token={raw_token}"
    subject = "Вход в KairaVPN"
    if purpose == "link_email":
        subject = "Подтверждение email для KairaVPN"
    try:
        email_sender.send_magic_link(email=email, subject=subject, link=verify_url)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to send magic link to %s: %s", email, exc)


def _now_ts() -> int:
    import time

    return int(time.time())

"""Centralised env loading and configuration for the web backend."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[4]
USER_BOT_ROOT = REPO_ROOT / "user_bot"


def _load_env() -> None:
    web_env = REPO_ROOT / "web" / "backend" / ".env"
    if web_env.exists():
        load_dotenv(dotenv_path=web_env, override=False)
    root_env = REPO_ROOT / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env, override=False)


def ensure_user_bot_on_path() -> None:
    """Make sure direct imports from user_bot work for adapters."""
    user_bot_path = str(USER_BOT_ROOT)
    if user_bot_path not in sys.path:
        sys.path.insert(0, user_bot_path)


_load_env()
ensure_user_bot_on_path()


class Settings:
    """Lightweight settings container backed by environment variables."""

    def __init__(self) -> None:
        self.web_env = os.getenv("WEB_ENV", "development")
        self.web_host = os.getenv("WEB_HOST", "127.0.0.1")
        self.web_port = int(os.getenv("WEB_PORT", "8000"))

        self.session_cookie_name = os.getenv("SESSION_COOKIE_NAME", "kairavpn_session")
        self.session_cookie_secure = (
            os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() == "true"
        )
        self.session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()

        self.jwt_secret = os.getenv("JWT_SECRET", "change_me")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expires_minutes = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))

        self.auth_rate_limit_max_requests = int(
            os.getenv("AUTH_RATE_LIMIT_MAX_REQUESTS", "10"),
        )
        self.auth_rate_limit_window_seconds = int(
            os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60"),
        )

        self.magic_link_ttl_minutes = int(os.getenv("MAGIC_LINK_TTL_MINUTES", "15"))
        self.tg_link_ttl_minutes = int(os.getenv("TG_LINK_TTL_MINUTES", "15"))

        self.app_base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
        self.api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.web_payment_return_url = (
            os.getenv("WEB_PAYMENT_RETURN_URL") or f"{self.app_base_url}/cabinet"
        ).strip()

        self.email_sender_mode = os.getenv("EMAIL_SENDER_MODE", "mock").strip().lower()
        self.email_app_name = os.getenv("EMAIL_APP_NAME", "KairaVPN").strip() or "KairaVPN"

        self.cors_origins = self._parse_cors(
            os.getenv("CORS_ORIGINS")
            or f"{self.app_base_url},http://127.0.0.1:3000,http://localhost:3000",
        )

        self.telegram_bot_token = os.getenv("USER_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
        self.telegram_bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        self.support_url = os.getenv("SUPPORT_URL", "https://t.me/nitratex1").strip()
        self.faq_url = os.getenv("FAQ_URL", "https://nitratex-company.gitbook.io/kairavpn/").strip()
        self.status_channel_url = os.getenv(
            "STATUS_CHANNEL_URL", "https://t.me/KairaVPN_channel"
        ).strip()

        self.yookassa_webhook_secret = (os.getenv("YOOKASSA_WEBHOOK_SECRET") or "").strip()
        self.yookassa_webhook_allowed_cidrs = (
            os.getenv("YOOKASSA_WEBHOOK_ALLOWED_CIDRS") or ""
        ).strip()

        self.trial_days = int(os.getenv("TRIAL_DAYS", "30"))

        self.vapid_public_key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
        self.vapid_private_key = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
        contact = (os.getenv("VAPID_CONTACT_EMAIL") or "").strip()
        if contact and not contact.startswith(("mailto:", "https://")):
            contact = f"mailto:{contact}"
        self.vapid_contact = contact

    @staticmethod
    def _parse_cors(raw: str) -> list[str]:
        return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def validate_required_env() -> None:
    """Fail fast on missing critical env values."""
    settings = get_settings()
    missing: list[str] = []
    if not settings.jwt_secret or settings.jwt_secret == "change_me":
        missing.append("JWT_SECRET")
    for key in ("YOOKASSA_SHOP_ID", "YOOKASSA_SECRET_KEY", "REMNAWAVE_BASE_URL"):
        if not (os.getenv(key) or "").strip():
            missing.append(key)
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set these values in web/backend/.env (or the repo root .env) before starting the API."
        )

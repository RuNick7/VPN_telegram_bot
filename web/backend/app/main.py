import hashlib
import hmac
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from email.utils import parseaddr
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.email_sender import get_email_sender
from app.services.payment_adapter import PaymentAdapterError, PaymentServiceAdapter
from app.services.subscription_adapter import SubscriptionAdapterError, SubscriptionServiceAdapter

load_dotenv()


SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "kairavpn_session")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))
AUTH_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_MAX_REQUESTS", "10"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60"))
TELEGRAM_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60
MAGIC_LINK_TTL_MINUTES = int(os.getenv("MAGIC_LINK_TTL_MINUTES", "15"))
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
EMAIL_SENDER_MODE = os.getenv("EMAIL_SENDER_MODE", "mock").strip().lower()
WEB_PAYMENT_RETURN_URL = os.getenv("WEB_PAYMENT_RETURN_URL", f"{APP_BASE_URL}/cabinet").strip()


app = FastAPI(title="KairaVPN Web API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

email_sender = get_email_sender()
logger = logging.getLogger(__name__)

_auth_rate_limit_storage: dict[str, deque[float]] = defaultdict(deque)
_protected_paths_exact = {"/api/me", "/api/subscription", "/api/auth/email/link"}
_protected_paths_prefix = ("/api/subscription/extend", "/api/payments/")
_telegram_profiles: dict[int, dict[str, Any]] = {}
_linked_email_by_telegram: dict[int, str] = {}
_telegram_by_email: dict[str, int] = {}
_magic_links_by_hash: dict[str, dict[str, Any]] = {}
subscription_adapter = SubscriptionServiceAdapter()
payment_adapter = PaymentServiceAdapter()


class TelegramAuthRequest(BaseModel):
    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class EmailLinkRequest(BaseModel):
    email: str


class MagicLinkRequest(BaseModel):
    email: str


class MagicLinkVerifyRequest(BaseModel):
    token: str


class ExtendSubscriptionRequest(BaseModel):
    months: int
    return_url: str | None = None


def _validate_required_env() -> None:
    required = [
        "YOOKASSA_SHOP_ID",
        "YOOKASSA_SECRET_KEY",
        "REMNAWAVE_BASE_URL",
    ]
    missing = [key for key in required if not (os.getenv(key) or "").strip()]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables: {missing_str}. "
            "Set these values in web/backend/.env before starting the API."
        )


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    ip = _get_client_ip(request)
    now = time.time()
    hits = _auth_rate_limit_storage[ip]

    while hits and now - hits[0] > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= AUTH_RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Too many auth attempts. Please try again later.",
        )

    hits.append(now)


def _normalize_email(raw_email: str) -> str:
    parsed_name, parsed_email = parseaddr(raw_email.strip())
    if parsed_name and "<" in raw_email and ">" in raw_email:
        # Prevent "Name <mail@domain>" format for simplicity in API contracts.
        parsed_email = ""
    email = parsed_email.lower().strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email.")
    return email


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _cleanup_expired_magic_links() -> None:
    now = int(time.time())
    expired = [token_hash for token_hash, data in _magic_links_by_hash.items() if data["expires_at"] <= now]
    for token_hash in expired:
        _magic_links_by_hash.pop(token_hash, None)


def _create_magic_link_token(*, purpose: str, telegram_id: int, email: str) -> tuple[str, int]:
    raw_token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + MAGIC_LINK_TTL_MINUTES * 60
    _magic_links_by_hash[_token_hash(raw_token)] = {
        "purpose": purpose,
        "telegram_id": telegram_id,
        "email": email,
        "expires_at": expires_at,
        "used_at": None,
    }
    return raw_token, expires_at


def _build_telegram_data_check_string(payload: TelegramAuthRequest) -> str:
    payload_dict = payload.model_dump(exclude_none=True)
    payload_dict.pop("hash", None)
    lines = [f"{k}={payload_dict[k]}" for k in sorted(payload_dict)]
    return "\n".join(lines)


def _validate_telegram_auth(payload: TelegramAuthRequest) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise HTTPException(status_code=401, detail="Telegram auth is not configured.")

    data_check_string = _build_telegram_data_check_string(payload)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, payload.hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature.")

    if int(time.time()) - int(payload.auth_date) > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram auth data is too old.")


def _issue_session_token(user_claims: dict[str, Any]) -> str:
    now = int(time.time())
    exp = now + JWT_EXPIRES_MINUTES * 60
    claims = {
        "sub": str(user_claims["telegram_id"]),
        "telegram_id": user_claims["telegram_id"],
        "username": user_claims.get("username"),
        "first_name": user_claims.get("first_name"),
        "last_name": user_claims.get("last_name"),
        "photo_url": user_claims.get("photo_url"),
        "email": user_claims.get("email"),
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_session_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    return claims


def _user_claims_for_telegram_id(telegram_id: int) -> dict[str, Any]:
    profile = _telegram_profiles.get(telegram_id, {})
    return {
        "telegram_id": telegram_id,
        "username": profile.get("username"),
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
        "photo_url": profile.get("photo_url"),
        "email": _linked_email_by_telegram.get(telegram_id),
    }


def _attach_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=JWT_EXPIRES_MINUTES * 60,
    )


def _send_magic_link_email(email: str, raw_token: str, purpose: str) -> None:
    verify_url = f"{APP_BASE_URL}/auth/magic-link/verify?token={raw_token}"
    subject = "KairaVPN sign-in link"
    if purpose == "link_email":
        subject = "KairaVPN confirm email link"
    email_sender.send_magic_link(email=email, subject=subject, link=verify_url)


def _is_protected_path(path: str) -> bool:
    if path in _protected_paths_exact:
        return True
    return any(path.startswith(prefix) for prefix in _protected_paths_prefix)


@app.on_event("startup")
async def startup_env_check() -> None:
    _validate_required_env()
    logger.info("startup_env_check_ok required_env=YOOKASSA_SHOP_ID,YOOKASSA_SECRET_KEY,REMNAWAVE_BASE_URL")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if _is_protected_path(request.url.path):
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized."})
        try:
            request.state.user = _decode_session_token(token)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": "Invalid request payload.", "errors": exc.errors()})


@app.get("/")
async def index() -> JSONResponse:
    return JSONResponse(
        {
            "service": "kairavpn-web-backend",
            "status": "ok",
            "message": "MVP web backend is running.",
        }
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "environment": os.getenv("WEB_ENV", "development"),
        }
    )


@app.post("/api/auth/telegram")
async def auth_telegram(payload: TelegramAuthRequest, request: Request) -> JSONResponse:
    _check_rate_limit(request)
    _validate_telegram_auth(payload)

    _telegram_profiles[payload.id] = {
        "username": payload.username,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "photo_url": payload.photo_url,
    }
    user_claims = _user_claims_for_telegram_id(payload.id)
    session_token = _issue_session_token(user_claims)

    response = JSONResponse(
        {
            "ok": True,
            "user": user_claims,
        }
    )
    _attach_session_cookie(response, session_token)
    return response


@app.post("/api/auth/email/link")
async def auth_email_link(payload: EmailLinkRequest, request: Request) -> JSONResponse:
    _cleanup_expired_magic_links()
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")

    telegram_id = int(user["telegram_id"])
    email = _normalize_email(payload.email)
    owner = _telegram_by_email.get(email)
    if owner is not None and owner != telegram_id:
        raise HTTPException(status_code=401, detail="Email is already linked to another account.")

    raw_token, expires_at = _create_magic_link_token(
        purpose="link_email",
        telegram_id=telegram_id,
        email=email,
    )
    _send_magic_link_email(email=email, raw_token=raw_token, purpose="link_email")

    body: dict[str, Any] = {
        "ok": True,
        "message": "Confirmation link sent.",
        "expires_in_seconds": max(0, expires_at - int(time.time())),
    }
    if EMAIL_SENDER_MODE == "mock":
        body["dev_magic_link_token"] = raw_token
    return JSONResponse(body)


@app.post("/api/auth/magic-link/request")
async def auth_magic_link_request(payload: MagicLinkRequest, request: Request) -> JSONResponse:
    _cleanup_expired_magic_links()
    _check_rate_limit(request)
    email = _normalize_email(payload.email)
    telegram_id = _telegram_by_email.get(email)

    body: dict[str, Any] = {"ok": True, "message": "If email is linked, a sign-in link was sent."}

    if telegram_id is not None:
        raw_token, expires_at = _create_magic_link_token(
            purpose="login_magic",
            telegram_id=telegram_id,
            email=email,
        )
        _send_magic_link_email(email=email, raw_token=raw_token, purpose="login_magic")
        body["expires_in_seconds"] = max(0, expires_at - int(time.time()))
        if EMAIL_SENDER_MODE == "mock":
            body["dev_magic_link_token"] = raw_token
    return JSONResponse(body)


@app.post("/api/auth/magic-link/verify")
async def auth_magic_link_verify(payload: MagicLinkVerifyRequest) -> JSONResponse:
    _cleanup_expired_magic_links()
    raw_token = payload.token.strip()
    if not raw_token:
        raise HTTPException(status_code=400, detail="Token is required.")

    token_hash = _token_hash(raw_token)
    token_data = _magic_links_by_hash.get(token_hash)
    if not token_data:
        raise HTTPException(status_code=401, detail="Magic link is invalid or expired.")
    if token_data.get("used_at") is not None:
        raise HTTPException(status_code=401, detail="Magic link was already used.")

    now = int(time.time())
    if token_data["expires_at"] <= now:
        _magic_links_by_hash.pop(token_hash, None)
        raise HTTPException(status_code=401, detail="Magic link is expired.")

    token_data["used_at"] = now
    purpose = token_data["purpose"]
    telegram_id = int(token_data["telegram_id"])
    email = str(token_data["email"])

    if purpose == "link_email":
        existing_owner = _telegram_by_email.get(email)
        if existing_owner is not None and existing_owner != telegram_id:
            raise HTTPException(status_code=401, detail="Email is already linked to another account.")
        _linked_email_by_telegram[telegram_id] = email
        _telegram_by_email[email] = telegram_id

    user_claims = _user_claims_for_telegram_id(telegram_id)
    session_token = _issue_session_token(user_claims)
    response = JSONResponse(
        {
            "ok": True,
            "purpose": purpose,
            "user": user_claims,
        }
    )
    _attach_session_cookie(response, session_token)
    return response


@app.get("/api/me")
async def get_me(request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")

    response: dict[str, Any] = {
        "telegram_id": user.get("telegram_id"),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "photo_url": user.get("photo_url"),
        "email": user.get("email"),
    }
    try:
        response["subscription"] = subscription_adapter.get_subscription_snapshot(int(user["telegram_id"]))
    except (SubscriptionAdapterError, ValueError) as exc:
        # Keep /api/me available even if subscription backend is temporarily unavailable.
        logger.warning("subscription_snapshot_failed telegram_id=%s reason=%s", user.get("telegram_id"), exc)
        response["subscription"] = None

    return JSONResponse(response)


@app.get("/api/subscription")
async def get_subscription(request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")

    try:
        subscription = subscription_adapter.get_subscription_snapshot(int(user["telegram_id"]))
    except (SubscriptionAdapterError, ValueError) as exc:
        logger.error("subscription_endpoint_failed telegram_id=%s reason=%s", user.get("telegram_id"), exc)
        raise HTTPException(status_code=502, detail="Subscription service unavailable.") from exc

    return JSONResponse(subscription)


@app.post("/api/subscription/extend")
async def create_extend_payment(payload: ExtendSubscriptionRequest, request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")

    months = int(payload.months)
    if months not in (1, 3, 6, 12):
        raise HTTPException(status_code=400, detail="Unsupported months value. Use one of: 1, 3, 6, 12.")
    return_url = (payload.return_url or WEB_PAYMENT_RETURN_URL).strip()
    if not return_url:
        raise HTTPException(status_code=400, detail="return_url is required.")

    telegram_id = int(user["telegram_id"])
    try:
        payment = payment_adapter.create_subscription_payment(
            telegram_id=telegram_id,
            months=months,
            return_url=return_url,
        )
    except PaymentAdapterError as exc:
        logger.error(
            "payment_create_failed telegram_id=%s months=%s return_url=%s reason=%s",
            telegram_id,
            months,
            return_url,
            exc,
        )
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

    logger.info(
        "Created payment %s for telegram_id=%s months=%s",
        payment.get("payment_id"),
        telegram_id,
        months,
    )
    return JSONResponse(
        {
            "payment_id": payment.get("payment_id"),
            "status": payment.get("status"),
            "confirmation_url": payment.get("confirmation_url"),
            "amount": payment.get("amount"),
            "days_to_extend": payment.get("days_to_extend"),
        }
    )


@app.get("/api/payments/{payment_id}")
async def get_payment_status(payment_id: str, request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized.")

    try:
        payment = payment_adapter.fetch_payment(payment_id=payment_id)
    except PaymentAdapterError as exc:
        logger.error("payment_fetch_failed payment_id=%s telegram_id=%s reason=%s", payment_id, user.get("telegram_id"), exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable.") from exc

    metadata = payment.get("metadata") or {}
    meta_telegram_id = metadata.get("telegram_id")
    if meta_telegram_id is not None and str(meta_telegram_id) != str(user["telegram_id"]):
        raise HTTPException(status_code=403, detail="Forbidden for this payment.")

    return JSONResponse(
        {
            "payment_id": payment.get("payment_id"),
            "status": payment.get("status"),
            "local_status": payment.get("local_status"),
            "metadata": metadata,
            "confirmation_url": payment.get("confirmation_url"),
        }
    )


@app.post("/api/payments/webhook/yookassa")
async def yookassa_webhook(request: Request) -> JSONResponse:
    request_ip = _get_client_ip(request)
    if not payment_adapter.is_allowed_source(request_ip):
        logger.warning("webhook_rejected_source source_ip=%s", request_ip)
        raise HTTPException(status_code=401, detail="Webhook source is not allowed.")

    header_secret = request.headers.get("x-kaira-webhook-secret")
    if not payment_adapter.is_valid_webhook_secret(header_secret):
        logger.warning("webhook_rejected_secret source_ip=%s", request_ip)
        raise HTTPException(status_code=401, detail="Webhook secret is invalid.")

    try:
        payload = await request.json()
    except Exception:
        logger.warning("webhook_invalid_json source_ip=%s", request_ip)
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = (payload or {}).get("event")
    payment_obj = (payload or {}).get("object") or {}
    payment_id = payment_obj.get("id")
    logger.info("webhook_received event=%s payment_id=%s source_ip=%s", event, payment_id, request_ip)
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment id in payload.")

    if event != "payment.succeeded":
        logger.info("webhook_ignored event=%s payment_id=%s source_ip=%s", event, payment_id, request_ip)
        return JSONResponse({"ok": True, "ignored": True, "event": event})

    try:
        processed = payment_adapter.process_webhook_success(payment_id=str(payment_id))
    except PaymentAdapterError as exc:
        logger.error("webhook_processing_failed event=%s payment_id=%s source_ip=%s reason=%s", event, payment_id, request_ip, exc)
        raise HTTPException(status_code=502, detail="Webhook processing failed.") from exc

    logger.info(
        "webhook_processed event=%s payment_id=%s status=%s idempotent=%s source_ip=%s",
        event,
        payment_id,
        processed.get("status"),
        processed.get("idempotent"),
        request_ip,
    )
    return JSONResponse(
        {
            "ok": True,
            "payment_id": str(payment_id),
            "status": processed.get("status"),
            "idempotent": bool(processed.get("idempotent")),
        }
    )

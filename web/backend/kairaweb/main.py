"""KairaVPN web API entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kairaweb.api.auth import router as auth_router
from kairaweb.api.gifts import router as gifts_router
from kairaweb.api.instructions import router as instructions_router
from kairaweb.api.internal import router as internal_router
from kairaweb.api.lte import router as lte_router
from kairaweb.api.me import router as me_router
from kairaweb.api.payments import router as payments_router
from kairaweb.api.push import router as push_router
from kairaweb.api.referrals import router as referrals_router
from kairaweb.api.servers import router as servers_router
from kairaweb.api.subscription import router as subscription_router
from kairaweb.core.security import decode_session_token
from kairaweb.core.settings import get_settings, validate_required_env


logger = logging.getLogger(__name__)

PROTECTED_PATH_EXACT = {
    "/api/me",
    "/api/subscription",
    "/api/subscription/tariffs",
    "/api/subscription/extend",
    "/api/lte/buy",
    "/api/gifts/buy",
    "/api/referrals",
    "/api/referrals/set",
    "/api/promo/redeem",
    "/api/servers",
    "/api/push/subscribe",
    "/api/push/unsubscribe",
}
PROTECTED_PATH_PREFIX = ("/api/payments/", "/api/instructions/")
PROTECTED_PATH_EXCLUDE_PREFIX = ("/api/payments/webhook",)


def _is_protected(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in PROTECTED_PATH_EXCLUDE_PREFIX):
        return False
    if path in PROTECTED_PATH_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PROTECTED_PATH_PREFIX)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="KairaVPN Web API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if _is_protected(request.url.path):
            token = request.cookies.get(settings.session_cookie_name)
            if not token:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized."})
            try:
                request.state.user = decode_session_token(token)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid request payload.", "errors": exc.errors()},
        )

    @app.on_event("startup")
    async def _startup() -> None:
        validate_required_env()
        logger.info("kairavpn_web_api startup ok env=%s", settings.web_env)

    @app.get("/")
    async def index() -> dict[str, Any]:
        return {"service": "kairavpn-web-api", "status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "healthy", "environment": settings.web_env}

    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(subscription_router)
    app.include_router(payments_router)
    app.include_router(lte_router)
    app.include_router(gifts_router)
    app.include_router(referrals_router)
    app.include_router(servers_router)
    app.include_router(instructions_router)
    app.include_router(push_router)
    app.include_router(internal_router)
    return app


app = create_app()

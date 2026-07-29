"""
One async Remnawave HTTP client, shared by both bots.

Replaces the two hand-rolled clients this project used to carry:
`admin_bot/app/api/client.py` (async, httpx) and
`user_bot/app/clients/remnawave/client.py` (sync, `requests`). This one keeps
admin_bot's URL normalization and error mapping, plus user_bot's
username/password login, token caching, and retry-after-401 -- which
admin_bot never had.

Being natively async is the point: user_bot's client was synchronous, so every
call site had to wrap it in `asyncio.to_thread` (and `vpn_service.py` had to
bridge its DB access back through `sync_bridge.run_sync`). Those wrappers go
away as call sites move onto this client.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .errors import (
    APIError,
    APINotFoundError,
    APIUnauthorizedError,
    UserNotFoundError,
    normalize_http_error,
)

logger = logging.getLogger(__name__)

# Hard ceiling on connection setup so an unreachable panel (dead DNS, dropped
# route) fails in seconds instead of hanging on the OS default. Carried over
# from user_bot's client, which is the only one of the two that had it.
_CONNECT_TIMEOUT_SECONDS = 5.0

# A login-issued token is reused for this long before re-authenticating. Without
# it, a single subscription extension cost three separate POST /auth/login
# round-trips.
_TOKEN_TTL_SECONDS = 900


def normalize_base_url(value: str) -> str:
    """
    Turn whatever is in REMNAWAVE_BASE_URL into a canonical `<origin>/api`.

    Accepts values with or without a scheme, and with or without a trailing
    `/api` -- both spellings appear in real deployments' .env files.
    """
    if not value or not value.strip():
        raise APIError("REMNAWAVE_BASE_URL is empty.")

    base_url = value.strip()
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"

    # Parse before trimming: stripping slashes off a bare `https://` first
    # would leave `https:`, which then reads as a hostname.
    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise APIError(f"Invalid REMNAWAVE_BASE_URL: {value}")

    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[: -len("/api")]
    return f"{parsed.scheme}://{parsed.netloc}{path}/api"


def normalize_token(value: str | None) -> str:
    """Strip an accidental `Bearer ` prefix -- people paste it in from docs."""
    token = (value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def unwrap(response: dict[str, Any]) -> Any:
    """
    Return a Remnawave payload's `response` envelope, or the payload itself.

    The panel wraps most successful bodies in `{"response": ...}`, but not all
    versions of every endpoint do -- both old clients checked for this
    individually at nearly every call site.
    """
    if isinstance(response, dict) and "response" in response:
        return response["response"]
    return response


class RemnawaveClient:
    """Async Remnawave panel client with token caching and 401 recovery."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: int = 5,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self._static_token = normalize_token(token)
        self._username = username
        self._password = password
        self._timeout_seconds = max(1, int(timeout_seconds))

        if not self._static_token and not (self._username and self._password):
            raise APIError(
                "Remnawave needs either REMNAWAVE_TOKEN/REMNAWAVE_API_KEY or "
                "REMNAWAVE_USERNAME + REMNAWAVE_PASSWORD."
            )

        self._client: httpx.AsyncClient | None = None
        self._cached_token: str | None = None
        self._cached_token_ts: float = 0.0
        # Serializes concurrent logins: without it, N handlers hitting a cold
        # cache at once each fire their own POST /auth/login.
        self._login_lock = asyncio.Lock()

    # -- transport ---------------------------------------------------------

    @property
    def _timeout(self) -> httpx.Timeout:
        read = float(self._timeout_seconds)
        return httpx.Timeout(read, connect=min(_CONNECT_TIMEOUT_SECONDS, max(2.0, read)))

    def _http(self) -> httpx.AsyncClient:
        """
        Lazily build the AsyncClient inside the running loop.

        Both bots instantiate their service singletons at import time, before
        any loop exists; an AsyncClient built there would bind to the wrong
        loop (or none).
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout)
        return self._client

    # -- auth --------------------------------------------------------------

    async def login(self) -> str:
        """Authenticate with username/password and cache the returned token."""
        if not (self._username and self._password):
            raise APIError("REMNAWAVE_USERNAME/REMNAWAVE_PASSWORD are not set.")

        response = await self._http().post(
            "/auth/login",
            json={"username": self._username, "password": self._password},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise normalize_http_error(exc) from exc

        token = normalize_token((unwrap(response.json()) or {}).get("accessToken"))
        if not token:
            raise APIError("Remnawave login succeeded but returned no accessToken.")
        self._cached_token = token
        self._cached_token_ts = time.monotonic()
        return token

    def invalidate_token(self) -> None:
        """Drop the cached login token, e.g. after the panel rejects it."""
        self._cached_token = None
        self._cached_token_ts = 0.0

    async def _ensure_token(self) -> str:
        if self._static_token:
            return self._static_token
        async with self._login_lock:
            if self._cached_token and (time.monotonic() - self._cached_token_ts) < _TOKEN_TTL_SECONDS:
                return self._cached_token
            return await self.login()

    # -- requests ----------------------------------------------------------

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """
        Issue an authenticated request, retrying once if the token is rejected.

        A 401 on a login-issued token means it expired mid-flight; re-login and
        replay. A 401 on a *static* token is a config problem, so it surfaces
        rather than looping.
        """
        token = await self._ensure_token()
        try:
            return await self._send(method, endpoint, token, **kwargs)
        except APIUnauthorizedError:
            if self._static_token or not (self._username and self._password):
                raise
            logger.warning("Remnawave rejected the cached token on %s %s; re-authenticating", method, endpoint)
            self.invalidate_token()
            return await self._send(method, endpoint, await self.login(), **kwargs)

    async def _send(self, method: str, endpoint: str, token: str, **kwargs: Any) -> dict[str, Any]:
        headers = {**kwargs.pop("headers", {}), "Authorization": f"Bearer {token}"}
        try:
            response = await self._http().request(method, endpoint, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise normalize_http_error(exc) from exc
        except httpx.RequestError as exc:
            message = str(exc) or type(exc).__name__
            raise APIError(
                f"Request failed: {message} (base_url={self.base_url}, endpoint={endpoint})"
            ) from exc
        if not response.content:
            return {}
        return response.json()

    # -- users -------------------------------------------------------------

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        """
        Look a user up by panel username. Raises UserNotFoundError on 404.

        Some panel versions nest the user under `response.user`, others return
        its fields directly under `response`.
        """
        try:
            payload = unwrap(await self.request("GET", f"/users/by-username/{username}"))
        except APINotFoundError as exc:
            raise UserNotFoundError(f"User not found: {username}") from exc
        if isinstance(payload, dict) and isinstance(payload.get("user"), dict):
            payload = payload["user"]
        if not isinstance(payload, dict) or not payload.get("uuid"):
            raise UserNotFoundError(f"User not found: {username}")
        return payload

    async def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Same as get_user_by_username but returns None instead of raising."""
        try:
            return await self.get_user_by_username(username)
        except UserNotFoundError:
            return None

    async def get_user_by_uuid(self, user_uuid: str) -> dict[str, Any]:
        return unwrap(await self.request("GET", f"/users/{user_uuid}"))

    async def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return unwrap(await self.request("POST", "/users", json=payload))

    async def update_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return unwrap(await self.request("PATCH", "/users", json=payload))

    async def delete_user(self, user_uuid: str) -> dict[str, Any]:
        return unwrap(await self.request("DELETE", f"/users/{user_uuid}"))

    async def list_users(self, page: int = 1, size: int = 100) -> dict[str, Any]:
        """Return one page as `{"users": [...], "total": N}` (envelope removed)."""
        params = {"page": page, "size": size, "limit": size}
        return unwrap(await self.request("GET", "/users", params=params)) or {}

    async def iter_all_users(self, size: int = 100):
        """Yield every user across all pages, one page-fetch at a time."""
        page = 1
        while True:
            data = await self.list_users(page=page, size=size)
            users = data.get("users") or []
            for user in users:
                yield user
            total = data.get("total")
            if not total:
                return
            if page >= max(1, (total + size - 1) // size):
                return
            page += 1

    # -- subscriptions -----------------------------------------------------

    async def get_subscription_by_username(self, username: str) -> dict[str, Any]:
        try:
            return unwrap(await self.request("GET", f"/subscriptions/by-username/{username}"))
        except APINotFoundError as exc:
            raise UserNotFoundError(f"User not found: {username}") from exc

    # -- internal squads ---------------------------------------------------

    async def list_internal_squads(self) -> list[dict[str, Any]]:
        payload = unwrap(await self.request("GET", "/internal-squads"))
        if isinstance(payload, dict):
            return payload.get("internalSquads") or []
        return payload or []

    async def create_internal_squad(self, name: str, inbound_ids: list[str]) -> dict[str, Any]:
        return unwrap(
            await self.request("POST", "/internal-squads", json={"name": name, "inbounds": inbound_ids})
        ) or {}

    async def set_user_squads(self, user_uuids: list[str], squad_uuids: list[str]) -> dict[str, Any]:
        """Replace the given users' squad membership outright."""
        return await self.request(
            "POST",
            "/users/bulk/update-squads",
            json={"uuids": user_uuids, "activeInternalSquads": squad_uuids},
        )

    async def add_users_to_squad(self, squad_uuid: str, user_uuids: list[str]) -> dict[str, Any]:
        return await self.request(
            "POST",
            f"/internal-squads/{squad_uuid}/bulk-actions/add-users",
            json={"userUuids": user_uuids},
        )

    async def remove_users_from_squad(self, squad_uuid: str, user_uuids: list[str]) -> dict[str, Any]:
        return await self.request(
            "DELETE",
            f"/internal-squads/{squad_uuid}/bulk-actions/remove-users",
            json={"userUuids": user_uuids},
        )

    # -- system ------------------------------------------------------------

    async def get_system_stats(self) -> dict[str, Any]:
        return unwrap(await self.request("GET", "/system/stats")) or {}

    async def list_nodes(self) -> list[dict[str, Any]]:
        return unwrap(await self.request("GET", "/nodes")) or []

    # -- lifecycle ---------------------------------------------------------

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

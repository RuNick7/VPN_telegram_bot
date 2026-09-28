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
    UserLeftDisabledError,
    UserNotFoundError,
    normalize_http_error,
)

logger = logging.getLogger(__name__)

# How to take an account out of every inbound and put it straight back, newest
# spelling first. Each generation's pair is kept together, so a panel that
# answers one half is never handed the other half from a different API.
_TOGGLE_SPELLINGS: tuple[tuple[Any, Any], ...] = (
    (
        lambda ref: ("POST", f"/users/{ref}/actions/disable"),
        lambda ref: ("POST", f"/users/{ref}/actions/enable"),
    ),
    (
        lambda ref: ("PATCH", f"/users/disable/{ref}"),
        lambda ref: ("PATCH", f"/users/enable/{ref}"),
    ),
    (
        lambda ref: ("PATCH", f"/users/{ref}/disable"),
        lambda ref: ("PATCH", f"/users/{ref}/enable"),
    ),
)

# Accounts this process disabled and could not put back. Retried once per
# monitor pass by `flush_pending_enables`, so a panel that was unreachable for
# a moment does not cost a customer their access until somebody reads an alert.
_pending_enable: set[str] = set()

# How long an account stays out of every inbound before being put back, when
# the panel cannot say whether its sockets are gone yet.
#
# Long enough for the panel to push the removal to a node, short enough that
# somebody whose *other* servers are unaffected barely notices. The first
# version held for 61 milliseconds and achieved nothing at all: node and panel
# are eventually consistent, so a removal and an addition delivered together
# are applied as their sum.
_DISABLE_HOLD_SECONDS = 3.0

# Waits between a drop and re-asking whether anything survived it.
#
# `/connections/drop` answers 202 and does the work on the node afterwards, so
# the answer is never ready immediately -- but it is quick: measured against a
# live client, the session was gone within the first half-second. The later
# waits exist for a node that is busy or briefly unreachable, not for the
# normal case.
_DROP_VERIFY_DELAYS: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)

# The panel answers "who is connected" by asking its nodes, so the query is a
# job: it is started, then polled by the id it hands back.
_CONNECTION_JOB_POLLS = 20
_CONNECTION_JOB_INTERVAL = 0.4

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


# -- panel identifiers -----------------------------------------------------
#
# Two generations of Remnawave name users differently. Older ones give every
# user a `uuid`; newer ones dropped it and address users by a numeric `id`,
# which also changed the key several request bodies expect. Everything that
# differs is normalised here so the rest of the codebase keeps passing one
# opaque string around and never has to know which panel it is talking to.


def panel_ref(user: Any) -> str:
    """The identifier this panel uses for a user record, as a string."""
    if not isinstance(user, dict):
        return ""
    for key in ("uuid", "id"):
        value = user.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def is_numeric_ref(ref: Any) -> bool:
    """
    Whether a ref is a newer panel's numeric id.

    A UUID is never all digits, so one stored string is enough to work out
    later which spelling to send back -- no second column, and no need to
    record which panel produced it.
    """
    text = str(ref).strip()
    return bool(text) and text.isdigit()


def identify(ref: Any) -> dict[str, Any]:
    """Name a user in a request body the way the panel expects."""
    if is_numeric_ref(ref):
        return {"id": int(str(ref).strip())}
    return {"uuid": str(ref)}


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
        if not isinstance(payload, dict) or not panel_ref(payload):
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
        """
        Patch a user. The identifier is re-spelled for whichever panel this is.

        Callers pass `{"uuid": ref, ...}` because that is what the older API
        wanted. A newer panel answers "At least one of username, id must be
        provided" and wants the id as a *number*, so the key is rewritten here
        rather than at each of the call sites.
        """
        body = dict(payload)
        ref = body.pop("uuid", None)
        if ref is not None:
            body.update(identify(ref))
        return unwrap(await self.request("PATCH", "/users", json=body))

    async def delete_user(self, user_uuid: str) -> dict[str, Any]:
        return unwrap(await self.request("DELETE", f"/users/{user_uuid}"))

    async def list_users(self, page: int = 1, size: int = 100) -> dict[str, Any]:
        """
        Return one page as `{"users": [...], "total": N}` (envelope removed).

        `start` is a record offset, and the only one of the two the panel
        actually honours -- confirmed directly against production: `page`
        is silently ignored, so every "page" answered with the same first
        `size` users and `iter_all_users` never reached anyone past the
        first one. Both monitors iterate through this, so hundreds of
        accounts outside that first page were invisible to FREE-tier
        demotion and LTE enforcement alike, for as long as this went
        unnoticed. `page`/`size` stay this method's own interface -- every
        caller already speaks in pages -- only the wire parameter changes.
        """
        params = {"start": (page - 1) * size, "size": size, "limit": size}
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

    async def drop_connections(
        self, user_uuid: str, *, node_uuids: list[str] | None = None
    ) -> bool:
        """
        Destroy this user's live sockets on the nodes. Returns whether it ran.

        The real answer, and nothing under `/users/*` is: current Remnawave
        keeps this in its own `connections` module. The node looks up the
        addresses the user is connected from and destroys those sockets
        outright, which is the one thing that ends a session already in
        progress -- taking somebody out of an inbound only stops the *next*
        handshake, and a tunnel already up carries on regardless.

        `node_uuids` narrows it to particular nodes. Worth passing: a traffic
        quota is spent on metered nodes, and someone who exhausts it should
        lose those, not the ordinary servers their subscription still covers.

        Two things must hold on the far side, neither of them ours: the panel
        has to be new enough to expose the module, and the node's container
        needs CAP_NET_ADMIN or it cannot destroy a socket it did not open.
        Both failures are quiet, so this reports rather than raises.
        """
        # `userIds` is a list of numbers in the contract. A panel that names
        # users by UUID is an older generation that has no such module at all.
        if not is_numeric_ref(user_uuid):
            return False

        target: dict[str, Any] = (
            {"target": "specificNodes", "nodeUuids": list(node_uuids)}
            if node_uuids
            else {"target": "allNodes"}
        )
        try:
            await self.request(
                "POST",
                "/connections/drop",
                json={
                    "dropBy": {"by": "userIds", "userIds": [int(str(user_uuid).strip())]},
                    "targetNodes": target,
                },
            )
            return True
        except APIError as exc:
            logger.debug("drop-connections for %s failed: %s", user_uuid, exc)
            return False

    async def active_connections(
        self, user_uuid: str, *, node_uuids: list[str] | None = None
    ) -> list[str] | None:
        """
        The addresses this user currently holds a session from, or None.

        The panel does not know this from its own state -- it asks the nodes --
        so the question is a job: a POST starts it and a GET polls it by the id
        that comes back. Both halves are spelled `by-user`, which reads like a
        mistake and is not: the GET's path parameter is the job, not the user.

        `None` means the question could not be answered: a panel with no
        `connections` module, or a job that never finished. That is not the
        same answer as "nobody is connected" and must not be read as one --
        the caller decides what to do about not knowing.
        """
        if not is_numeric_ref(user_uuid):
            return None

        wanted = set(node_uuids or ())
        try:
            started = unwrap(await self.request("POST", f"/connections/by-user/{user_uuid}")) or {}
            job_id = started.get("jobId")
            if not job_id:
                return None
            for _ in range(_CONNECTION_JOB_POLLS):
                await asyncio.sleep(_CONNECTION_JOB_INTERVAL)
                job = unwrap(await self.request("GET", f"/connections/by-user/{job_id}")) or {}
                if not job.get("isCompleted"):
                    continue
                nodes = (job.get("result") or {}).get("nodes") or []
                return [
                    address["ip"]
                    for node in nodes
                    # A quota is spent on the metered nodes, so a session on
                    # any other one is legitimate and must not count as
                    # something that survived the drop.
                    if not wanted or node.get("nodeUuid") in wanted
                    for address in node.get("ips") or []
                    if address.get("ip")
                ]
        except APIError as exc:
            logger.debug("connections/by-user for %s failed: %s", user_uuid, exc)
        return None

    async def _drop_until_gone(
        self, user_uuid: str, *, node_uuids: list[str] | None = None
    ) -> bool:
        """
        Drop, ask whether it worked, drop again. True once nothing is left.

        `drop` answers 202 the instant the panel has queued it, which proves
        only that the panel accepted the instruction -- never that a socket
        died. Checking is the whole point of this method.
        """
        if not await self.drop_connections(user_uuid, node_uuids=node_uuids):
            # An older panel with no connections module. Nothing here can
            # destroy a socket, so the only lever left is time: hold the
            # account out long enough for the node to be handed the removal.
            await asyncio.sleep(_DISABLE_HOLD_SECONDS)
            return False

        for delay in _DROP_VERIFY_DELAYS:
            await asyncio.sleep(delay)
            live = await self.active_connections(user_uuid, node_uuids=node_uuids)
            if live is None:
                # Can't tell. Fall back to waiting, rather than reporting a
                # success nobody measured.
                await asyncio.sleep(_DISABLE_HOLD_SECONDS)
                return True
            if not live:
                return True
            logger.info(
                "Session for %s survived a drop (%s); dropping again",
                user_uuid, ", ".join(live),
            )
            await self.drop_connections(user_uuid, node_uuids=node_uuids)
        return False

    async def disconnect_user(self, user_uuid: str, *, node_uuids: list[str] | None = None) -> bool:
        """
        End this user's live sessions so that they stay ended.

        **Call this after applying a membership change, never before** -- the
        opposite of what this method used to ask for, and the reason a blocked
        user kept browsing.

        A node learns what a user is entitled to only when the panel pushes it,
        and the panel pushes on a *status* change. Taking somebody out of a
        squad is recorded and not pushed: measured against a live client, the
        session ran on for two minutes afterwards, and `/connections/drop`
        alone did not help -- the socket died and the client, still listed in
        the inbound, reconnected inside five seconds. Disabling the account is
        what removes it from every inbound the node holds; the drop is what
        ends the tunnel that is already up. Neither is sufficient alone.

        So: disable, drop, check the sockets are gone, enable. The enable
        re-pushes whatever squads the user has *now*, which is why the
        membership change has to be in place before this is called. Measured
        against the same live client, that combination held for two minutes
        with the client retrying, and it reconnected within five seconds of the
        squad being handed back -- so the block was the block, not a broken
        client.

        The risk is the obvious one, and `legacy-main` shipped it unguarded: if
        `enable` does not land after `disable` did, the account has no access at
        all and nothing puts it back. So the enable is retried, and a user still
        disabled afterwards is both remembered for the next pass and raised as
        its own error rather than counted among ordinary per-user failures.
        """
        for disable, enable in _TOGGLE_SPELLINGS:
            try:
                await self.request(*disable(user_uuid))
            except APIError as exc:
                logger.debug("disable via %s failed: %s", disable(user_uuid)[1], exc)
                continue

            try:
                dropped = await self._drop_until_gone(user_uuid, node_uuids=node_uuids)
            finally:
                # Whatever the drop did, the account has to come back. This is
                # the half whose failure costs a customer their access.
                restored = await self._enable_with_retries(user_uuid, enable)

            if not restored:
                _pending_enable.add(user_uuid)
                raise UserLeftDisabledError(
                    f"Отключил пользователя {user_uuid}, но не смог включить обратно. "
                    "Доступа нет до повторной попытки или ручного включения в панели."
                )
            _pending_enable.discard(user_uuid)
            return dropped

        logger.warning("Could not disconnect user %s: no known endpoint accepted it", user_uuid)
        return False

    async def _enable_with_retries(self, user_uuid: str, enable: Any, attempts: int = 4) -> bool:
        """Put an account back, trying harder than once. True if it is enabled."""
        for attempt in range(attempts):
            try:
                await self.request(*enable(user_uuid))
                return True
            except APIError as exc:
                # "Already enabled" is the panel disagreeing about wording, not
                # a failure: the account is in the state we want it in.
                if "already enabled" in str(exc).lower():
                    return True
                logger.warning(
                    "Re-enabling %s failed (attempt %d/%d): %s",
                    user_uuid, attempt + 1, attempts, exc,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return False

    async def flush_pending_enables(self) -> list[str]:
        """
        Re-enable anyone an earlier flip left disabled. Returns those still stuck.

        Only accounts this process disabled itself are touched, which is what
        keeps it from quietly undoing an operator who disabled someone in the
        panel on purpose. A monitor calls this once per pass, so a panel that
        was briefly unreachable heals on its own within one interval instead of
        leaving a customer with nothing until somebody reads an alert.
        """
        if not _pending_enable:
            return []

        stuck: list[str] = []
        for user_uuid in sorted(_pending_enable):
            for _, enable in _TOGGLE_SPELLINGS:
                if await self._enable_with_retries(user_uuid, enable, attempts=1):
                    _pending_enable.discard(user_uuid)
                    logger.info("Re-enabled %s after an earlier failure", user_uuid)
                    break
            else:
                stuck.append(user_uuid)
        return stuck

    # -- subscriptions -----------------------------------------------------

    async def get_subscription_by_username(self, username: str) -> dict[str, Any]:
        try:
            return unwrap(await self.request("GET", f"/subscriptions/by-username/{username}"))
        except APINotFoundError as exc:
            raise UserNotFoundError(f"User not found: {username}") from exc

    async def revoke_subscription(self, user_uuid: str) -> dict[str, Any]:
        """
        Issue the user a new subscription link and kill the old one.

        Sent without a body on purpose: the panel then generates the new short
        UUID itself, which its own docs recommend over supplying one.

        This rotates the link only. Expiry, traffic counters and squad
        membership are untouched, and registered devices survive -- they simply
        stop working until the new link is imported.
        """
        return unwrap(await self.request("POST", f"/users/{user_uuid}/actions/revoke"))

    # -- devices (HWID) ----------------------------------------------------

    async def list_hwid_devices(self, user_uuid: str) -> list[dict[str, Any]]:
        """
        Devices registered against a user, newest field set as the panel gives it.

        A 404 reads as "none": panels with HWID tracking switched off answer
        that way, and an empty device list is the honest thing to show for
        them. Deletion below is strict for the same reason in reverse -- there
        a silent no-op would tell the user something happened that didn't.
        """
        try:
            payload = unwrap(await self.request("GET", f"/hwid/devices/{user_uuid}"))
        except APINotFoundError:
            logger.info("No HWID devices endpoint/response for user %s", user_uuid)
            return []
        if isinstance(payload, dict):
            return payload.get("devices") or []
        return payload or []

    async def delete_hwid_device(self, user_uuid: str, hwid: str) -> None:
        """Unregister one device. Raises if the panel did not accept it."""
        await self.request(
            "POST",
            "/hwid/devices/delete",
            json={
                "hwid": hwid,
                **({"userId": int(user_uuid)} if is_numeric_ref(user_uuid) else {"userUuid": user_uuid}),
            },
        )

    # -- internal squads ---------------------------------------------------

    async def list_internal_squads(self) -> list[dict[str, Any]]:
        payload = unwrap(await self.request("GET", "/internal-squads"))
        if isinstance(payload, dict):
            return payload.get("internalSquads") or []
        return payload or []

    async def set_user_squads(self, user_uuids: list[str], squad_uuids: list[str]) -> dict[str, Any]:
        """Replace the given users' squad membership outright."""
        # `uuids` on older panels, `userIds` with numbers on newer ones. Squads
        # themselves kept their UUIDs across that change, so only the user side
        # of this body varies.
        if user_uuids and all(is_numeric_ref(ref) for ref in user_uuids):
            key, values = "userIds", [int(str(ref)) for ref in user_uuids]
        else:
            key, values = "uuids", [str(ref) for ref in user_uuids]
        return await self.request(
            "POST",
            "/users/bulk/update-squads",
            json={key: values, "activeInternalSquads": squad_uuids},
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

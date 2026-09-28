"""Remnawave client behaviour that doesn't need a live panel."""

import json

import httpx
import pytest

from tgvpn_shared.remnawave import (
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIServerError,
    APIUnauthorizedError,
    RemnawaveClient,
    UserNotFoundError,
    normalize_base_url,
    normalize_http_error,
    normalize_token,
    unwrap,
)


@pytest.mark.parametrize(
    "raw",
    [
        "https://panel.example.com",
        "https://panel.example.com/",
        "https://panel.example.com/api",
        "https://panel.example.com/api/",
        "panel.example.com",
    ],
)
def test_base_url_normalizes_to_single_api_suffix(raw):
    """All the spellings that show up in real .env files land on one form."""
    assert normalize_base_url(raw) == "https://panel.example.com/api"


@pytest.mark.parametrize("raw", ["", "   ", "https://"])
def test_base_url_rejects_unusable_values(raw):
    with pytest.raises(APIError):
        normalize_base_url(raw)


def test_token_strips_pasted_bearer_prefix():
    assert normalize_token("Bearer abc123") == "abc123"
    assert normalize_token("bearer  abc123 ") == "abc123"
    assert normalize_token("  abc123  ") == "abc123"
    assert normalize_token(None) == ""


def test_unwrap_handles_both_envelope_shapes():
    assert unwrap({"response": {"uuid": "u"}}) == {"uuid": "u"}
    assert unwrap({"uuid": "u"}) == {"uuid": "u"}


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, APIUnauthorizedError),
        (404, APINotFoundError),
        (429, APIRateLimitError),
        (500, APIServerError),
        (503, APIServerError),
        (418, APIError),
    ],
)
def test_http_errors_map_onto_the_hierarchy(status, expected):
    request = httpx.Request("GET", "https://panel.example.com/api/users")
    response = httpx.Response(status, json={"message": "boom"}, request=request)
    error = normalize_http_error(httpx.HTTPStatusError("x", request=request, response=response))
    assert isinstance(error, expected)
    assert "boom" in str(error)


def test_client_requires_some_credential():
    with pytest.raises(APIError):
        RemnawaveClient(base_url="https://panel.example.com")


def test_client_accepts_username_password_without_token():
    client = RemnawaveClient(
        base_url="https://panel.example.com", username="admin", password="secret"
    )
    assert client.base_url == "https://panel.example.com/api"


def _client_with_transport(handler, **kwargs) -> RemnawaveClient:
    """A client whose HTTP layer is a scripted MockTransport."""
    client = RemnawaveClient(base_url="https://panel.example.com", **kwargs)
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    return client


async def test_get_user_by_username_raises_user_not_found_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    client = _client_with_transport(handler, token="tok")
    with pytest.raises(UserNotFoundError):
        await client.get_user_by_username("123456789")
    await client.close()


async def test_find_user_by_username_returns_none_instead_of_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    client = _client_with_transport(handler, token="tok")
    assert await client.find_user_by_username("123456789") is None
    await client.close()


async def test_expired_login_token_triggers_one_retry():
    """
    A 401 on a login-issued token means it expired; re-login and replay once.

    This is the behaviour user_bot's old sync client had and admin_bot's async
    one did not -- the merged client keeps it.
    """
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if path.endswith("/auth/login"):
            token = "fresh" if len(calls) > 1 else "stale"
            return httpx.Response(200, json={"response": {"accessToken": token}})
        if request.headers.get("Authorization") == "Bearer stale":
            return httpx.Response(401, json={"message": "token expired"})
        return httpx.Response(200, json={"response": {"users": [], "total": 0}})

    client = _client_with_transport(handler, username="admin", password="secret")
    result = await client.list_users()

    assert result == {"users": [], "total": 0}
    # login -> users(401) -> login -> users(200)
    assert calls == ["/api/auth/login", "/api/users", "/api/auth/login", "/api/users"]
    await client.close()


async def test_static_token_401_is_not_retried():
    """A rejected static token is a config error, so it surfaces immediately."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(401, json={"message": "bad token"})

    client = _client_with_transport(handler, token="wrong")
    with pytest.raises(APIUnauthorizedError):
        await client.list_users()
    assert calls == ["/api/users"]
    await client.close()


async def test_login_token_is_cached_across_requests():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/auth/login"):
            return httpx.Response(200, json={"response": {"accessToken": "tok"}})
        return httpx.Response(200, json={"response": {"users": [], "total": 0}})

    client = _client_with_transport(handler, username="admin", password="secret")
    await client.list_users()
    await client.list_users()

    assert calls.count("/api/auth/login") == 1
    await client.close()


async def test_iter_all_users_walks_every_page():
    """
    Paged by record offset, not by page number.

    The panel ignores `page` outright -- confirmed directly against
    production, where every "page" answered with the same first `size`
    users and `iter_all_users` silently never reached anyone past the
    first one. `start` is the offset it actually honours, so that is what
    this fake server keys off of; a handler that (wrongly) branched on
    `page` instead would pass even though the real panel does not.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params.get("start", 0))
        users = [{"uuid": f"u{start + i}"} for i in range(2)] if start < 4 else []
        return httpx.Response(200, json={"response": {"users": users, "total": 4}})

    client = _client_with_transport(handler, token="tok")
    uuids = [user["uuid"] async for user in client.iter_all_users(size=2)]
    assert uuids == ["u0", "u1", "u2", "u3"]
    await client.close()


async def test_list_users_sends_a_record_offset_not_a_page_number():
    """
    Pins the exact wire parameter, since this is the regression that made
    `iter_all_users` a no-op past the first page for months: a fake server
    keyed on the wrong field would not have caught it, only one that
    inspects the actual request does.
    """
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"response": {"users": [], "total": 0}})

    client = _client_with_transport(handler, token="tok")
    await client.list_users(page=3, size=25)
    await client.close()

    assert seen[-1]["start"] == "50"
    assert seen[-1]["size"] == "25"


async def test_connectivity_failures_surface_as_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    client = _client_with_transport(handler, token="tok")
    with pytest.raises(APIError) as excinfo:
        await client.list_users()
    assert "Request failed" in str(excinfo.value)
    await client.close()


# -- subscription reset and devices ----------------------------------------


async def test_revoke_posts_without_a_body_and_returns_the_new_link():
    """
    No body on purpose: the panel then generates the new short UUID itself,
    which its own documentation recommends over supplying one.
    """
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["content"] = request.content
        return httpx.Response(200, json={"response": {"subscriptionUrl": "https://sub/new"}})

    client = _client_with_transport(handler, token="tok")
    result = await client.revoke_subscription("uuid-1")

    assert seen["method"] == "POST"
    assert seen["path"] == "/api/users/uuid-1/actions/revoke"
    assert seen["content"] == b""
    assert result["subscriptionUrl"] == "https://sub/new"
    await client.close()


async def test_devices_are_unwrapped_from_the_envelope():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"response": {"devices": [{"hwid": "a"}, {"hwid": "b"}], "total": 2}}
        )

    client = _client_with_transport(handler, token="tok")
    assert [d["hwid"] for d in await client.list_hwid_devices("uuid-1")] == ["a", "b"]
    await client.close()


async def test_a_panel_without_device_tracking_reports_no_devices():
    """
    A 404 here reads as "none". Panels with HWID tracking switched off answer
    that way, and an empty list is the honest thing to show for them.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    client = _client_with_transport(handler, token="tok")
    assert await client.list_hwid_devices("uuid-1") == []
    await client.close()


async def test_deleting_a_device_names_both_the_user_and_the_device():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["json"] = json.loads(request.content)
        return httpx.Response(200, json={"response": {"devices": [], "total": 0}})

    client = _client_with_transport(handler, token="tok")
    await client.delete_hwid_device("uuid-1", "HW-123")

    assert seen["path"] == "/api/hwid/devices/delete"
    assert seen["json"] == {"userUuid": "uuid-1", "hwid": "HW-123"}
    await client.close()


async def test_a_refused_device_deletion_raises_rather_than_passing_silently():
    """
    The opposite of the listing case above: a silent no-op here would tell the
    user their device was removed when it was not.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    client = _client_with_transport(handler, token="tok")
    with pytest.raises(APINotFoundError):
        await client.delete_hwid_device("uuid-1", "HW-123")
    await client.close()

"""Remnawave API errors, normalized from httpx failures."""

from __future__ import annotations

import httpx


class APIError(Exception):
    """Base Remnawave API error."""


class APIUnauthorizedError(APIError):
    """401 Unauthorized -- the panel token is missing, expired, or rejected."""


class APINotFoundError(APIError):
    """404 Not Found."""


class APIRateLimitError(APIError):
    """429 Too Many Requests."""


class APIServerError(APIError):
    """5xx Server error."""


class UserNotFoundError(APINotFoundError):
    """
    A user lookup returned 404.

    Split out from the generic 404 because both bots branch on exactly this
    case (create the profile instead of failing). Before Phase 2 the two
    clients signalled it inconsistently -- admin_bot raised APINotFoundError
    while user_bot raised `ValueError("User not found")`, and several call
    sites matched on the literal string. Callers can now catch the type.
    """


def normalize_http_error(exc: httpx.HTTPStatusError) -> APIError:
    """Map an httpx status error onto the error hierarchy above."""
    status_code = exc.response.status_code

    message = f"API request failed with status {status_code}"
    try:
        body = exc.response.json()
        if isinstance(body, dict):
            message = body.get("message") or body.get("error") or message
    except Exception:
        message = exc.response.text or message

    if status_code == 401:
        return APIUnauthorizedError(message)
    if status_code == 404:
        return APINotFoundError(message)
    if status_code == 429:
        return APIRateLimitError(message)
    if 500 <= status_code < 600:
        return APIServerError(message)
    return APIError(f"{message} (status: {status_code})")

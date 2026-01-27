"""API error handling and normalization."""

import httpx
from typing import Optional


class APIError(Exception):
    """Base API error."""
    pass


class APIUnauthorizedError(APIError):
    """401 Unauthorized error."""
    pass


class APINotFoundError(APIError):
    """404 Not Found error."""
    pass


class APIRateLimitError(APIError):
    """429 Rate Limit error."""
    pass


class APIServerError(APIError):
    """5xx Server error."""
    pass


def handle_api_error(http_error: httpx.HTTPStatusError) -> APIError:
    """Normalize HTTP errors to API error types."""
    status_code = http_error.response.status_code

    error_message = f"API request failed with status {status_code}"
    try:
        error_body = http_error.response.json()
        if "message" in error_body:
            error_message = error_body["message"]
        elif "error" in error_body:
            error_message = error_body["error"]
    except Exception:
        error_message = http_error.response.text or error_message

    if status_code == 401:
        return APIUnauthorizedError(error_message)
    elif status_code == 404:
        return APINotFoundError(error_message)
    elif status_code == 429:
        return APIRateLimitError(error_message)
    elif 500 <= status_code < 600:
        return APIServerError(error_message)
    else:
        return APIError(f"{error_message} (status: {status_code})")

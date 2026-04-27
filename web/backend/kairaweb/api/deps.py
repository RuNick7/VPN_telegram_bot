"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from kairaweb.core.security import get_user_from_request


def current_user(request: Request) -> dict:
    return get_user_from_request(request)


CurrentUser = Depends(current_user)

"""Servers (Remnawave squads) overview."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from kairaweb.api.deps import current_user
from kairaweb.services.servers import list_servers_for_user


router = APIRouter(prefix="/api", tags=["servers"])
logger = logging.getLogger(__name__)


@router.get("/servers")
async def servers(request: Request, user=current_user) -> dict[str, Any]:
    items = await list_servers_for_user(int(user["telegram_id"]))
    return {"servers": items}

"""Servers (Remnawave squads) overview for the web cabinet."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kairaweb.core.settings import ensure_user_bot_on_path

ensure_user_bot_on_path()

from app.config.settings import get_remnawave_settings  # noqa: E402  (user_bot)
from app.services.remnawave import vpn_service  # noqa: E402  (user_bot)


logger = logging.getLogger(__name__)
REMNAWAVE_CALL_TIMEOUT_SECONDS = 10.0


async def _to_thread(func, *args, **kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(func, *args, **kwargs),
        timeout=REMNAWAVE_CALL_TIMEOUT_SECONDS,
    )


def _classify_squad(name: str, settings) -> str:
    name = (name or "").strip()
    if name == settings.lte_squad_name:
        return "lte"
    if name == settings.free_squad_name:
        return "free"
    if name.startswith(f"{settings.internal_squad_prefix}-"):
        return "paid"
    return "other"


async def list_servers_for_user(telegram_id: int) -> list[dict[str, Any]]:
    settings = get_remnawave_settings()
    client = vpn_service._client()
    try:
        token = await _to_thread(client.ensure_token)
        all_squads = await _to_thread(vpn_service._list_internal_squads, client, token)
        try:
            user_resp = await _to_thread(
                client.get_user_by_username, str(telegram_id), token_override=token
            )
        except Exception as exc:
            if "User not found" in str(exc):
                user_resp = {}
            else:
                raise
    except Exception as exc:
        logger.warning("[servers] Remnawave call failed: %s", exc)
        return []

    user_obj = (user_resp or {}).get("response") or {}
    user_squads = {
        str(s.get("uuid"))
        for s in (user_obj.get("activeInternalSquads") or [])
        if s.get("uuid")
    }

    paid_squads_present = any(
        _classify_squad(s.get("name") or "", settings) == "paid"
        and str(s.get("uuid")) in user_squads
        for s in all_squads
    )

    result: list[dict[str, Any]] = []
    for squad in all_squads:
        name = str(squad.get("name") or "")
        kind = _classify_squad(name, settings)
        members = vpn_service._members_count(squad)
        squad_uuid = str(squad.get("uuid") or "")
        is_user_in = squad_uuid in user_squads
        if kind == "paid":
            available = is_user_in or paid_squads_present
        elif kind == "lte":
            available = is_user_in
        elif kind == "free":
            available = True
        else:
            available = is_user_in

        result.append(
            {
                "uuid": squad_uuid,
                "name": name,
                "display_name": _display_name(name, kind),
                "kind": kind,
                "members": members,
                "available": bool(available),
                "is_active": is_user_in,
            }
        )
    return sorted(result, key=lambda item: (_kind_order(item["kind"]), item["name"]))


def _display_name(name: str, kind: str) -> str:
    if kind == "free":
        return "FREE"
    if kind == "lte":
        return "LTE"
    if kind == "paid":
        return name.upper()
    return name


def _kind_order(kind: str) -> int:
    return {"paid": 0, "lte": 1, "free": 2}.get(kind, 3)

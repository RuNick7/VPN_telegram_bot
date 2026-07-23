"""
Subscription expiration monitor.

Panel-side expireAt is held at INFINITE_EXPIRE_DATE for everyone; the source of
truth for whether a user is actually paid is `subscription_ends` in the local
SQLite DB (user_bot data). This job reconciles every Remnawave user with the
DB once per cycle:

- expired user (subscription_ends <= now)
    → strip every paid squad (`internal-*`, `LTE`, ...) and put the user into
      a single FREE squad (limited free servers configured by admin in panel).
      Active sessions are force-disconnected so they cannot keep using paid
      servers via cached connections.
- active user (subscription_ends > now)
    → ensure the user is in a paid `internal-*` squad. If they were demoted to
      FREE earlier, FREE is removed and they are reassigned to a paid squad
      with capacity. LTE squad membership is left to the LTE traffic monitor.

The job is idempotent: if the user is already in the desired state nothing is
sent to the API.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config.settings import settings
from app.notify.admin import send_admin_message
from app.services.subscription_db import get_subscription_ends_map
from app.services.users import user_service

logger = logging.getLogger(__name__)


def _extract_tg_id(user: dict[str, Any]) -> int | None:
    for key in ("telegramId", "telegram_id"):
        value = user.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    username = str(user.get("username") or "").strip()
    if username.isdigit():
        return int(username)
    return None


def _extract_user_squad_uuids(user: dict[str, Any]) -> list[str]:
    squads = user.get("activeInternalSquads") or []
    return [str(s.get("uuid")) for s in squads if s.get("uuid")]


async def _list_all_users() -> list[dict[str, Any]]:
    page = 1
    size = 100
    users: list[dict[str, Any]] = []
    while True:
        response = await user_service.list_users(page=page, size=size)
        payload = response.get("response", {})
        batch = payload.get("users", []) or []
        if not isinstance(batch, list):
            break
        users.extend([item for item in batch if isinstance(item, dict)])
        total = payload.get("total")
        if not isinstance(total, int) or total <= page * size:
            break
        page += 1
    return users


async def _resolve_squads() -> tuple[str | None, set[str]]:
    """
    Return (free_squad_uuid, paid_internal_squad_uuids).

    `paid_internal_squad_uuids` includes only `internal-*` squads. LTE and any
    custom paid squads are handled separately and left untouched here.
    """
    squads = await user_service._list_internal_squads()
    free_uuid: str | None = None
    paid: set[str] = set()
    free_name = (settings.free_squad_name or "FREE").strip().lower()
    for squad in squads:
        name = str(squad.get("name") or "").strip()
        uuid = squad.get("uuid")
        if not uuid:
            continue
        if name.lower() == free_name:
            free_uuid = str(uuid)
            continue
        if user_service._is_paid_internal_squad(squad):
            paid.add(str(uuid))
    return free_uuid, paid


async def _pick_paid_internal_squad_uuid() -> str | None:
    """Re-use the same auto-pick / auto-create logic that user creation uses."""
    squad, _created = await user_service._get_or_create_internal_squad()
    if not squad:
        return None
    uuid = squad.get("uuid")
    return str(uuid) if uuid else None


async def run_subscription_expire_monitor() -> None:
    """Reconcile panel squads with the local subscription_ends ground truth."""
    if not settings.subscription_expire_monitor_enabled:
        return

    now = int(time.time())
    demoted = 0
    promoted = 0
    failures: list[str] = []

    try:
        free_squad_uuid, paid_squad_uuids = await _resolve_squads()
        if not free_squad_uuid:
            logger.warning(
                "FREE squad '%s' not found; skipping subscription expire monitor",
                settings.free_squad_name,
            )
            return

        ends_map = await get_subscription_ends_map()
        users = await _list_all_users()

        for user in users:
            user_uuid = user.get("uuid")
            if not user_uuid:
                continue
            tg_id = _extract_tg_id(user)
            if tg_id is None:
                continue

            sub_ends_ts = ends_map.get(tg_id, 0)
            current_squads = _extract_user_squad_uuids(user)
            current_set = set(current_squads)
            in_free = free_squad_uuid in current_set
            in_paid = bool(paid_squad_uuids & current_set)

            try:
                if sub_ends_ts <= now:
                    # Subscription expired → demote to FREE only.
                    desired = [free_squad_uuid]
                    if in_paid or not in_free or set(desired) != current_set:
                        await user_service._update_user_internal_squads(
                            str(user_uuid), desired
                        )
                        await user_service.force_disconnect_user(str(user_uuid))
                        demoted += 1
                        logger.info(
                            "Demoted tg_id=%s to FREE (was in %s)",
                            tg_id,
                            current_squads,
                        )
                else:
                    # Subscription active → must have at least one paid squad.
                    if in_paid:
                        # Already paid; ensure FREE is not lingering.
                        if in_free:
                            new_squads = [
                                uuid for uuid in current_squads if uuid != free_squad_uuid
                            ]
                            await user_service._update_user_internal_squads(
                                str(user_uuid), new_squads
                            )
                            promoted += 1
                            logger.info(
                                "Cleaned up FREE squad for active tg_id=%s", tg_id
                            )
                        continue

                    # Active subscription but no paid squad: promote.
                    paid_uuid = await _pick_paid_internal_squad_uuid()
                    if not paid_uuid:
                        failures.append(f"{tg_id}: no paid squad available")
                        continue
                    new_squads = [
                        uuid for uuid in current_squads if uuid != free_squad_uuid
                    ]
                    if paid_uuid not in new_squads:
                        new_squads.append(paid_uuid)
                    await user_service._update_user_internal_squads(
                        str(user_uuid), new_squads
                    )
                    promoted += 1
                    logger.info(
                        "Promoted tg_id=%s to paid squad %s", tg_id, paid_uuid
                    )
            except Exception as exc:
                failures.append(f"{tg_id}: {exc}")
                logger.warning("Failed to reconcile tg_id=%s: %s", tg_id, exc)

        if demoted or promoted or failures:
            lines = [
                "🛡 Подписка-монитор:",
                f"• демотировано в FREE: {demoted}",
                f"• возвращено в платный: {promoted}",
            ]
            if failures:
                lines.append(f"• ошибок: {len(failures)}")
                preview = failures[:5]
                lines.extend([f"  — {item}" for item in preview])
                if len(failures) > len(preview):
                    lines.append(f"  … и ещё {len(failures) - len(preview)}")
            await send_admin_message("\n".join(lines))
    except Exception as exc:
        logger.error("Subscription expire monitor failed: %s", exc, exc_info=True)
        await send_admin_message(
            "❌ Ошибка subscription-monitor.\n"
            f"Причина: {exc}"
        )

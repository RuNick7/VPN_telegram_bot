"""
Delete panel accounts nobody is paying for.

With the FREE tier on, a lapsed subscription no longer costs the user their
account -- they fall back to the free servers and stay there. That is the
point of the feature, and it is also why this job still exists: without it the
free squad accumulates every account that has ever lapsed, and the servers
behind it fill up with people who stopped paying a year ago.

The rule is one month on the free servers. Concretely: `subscription_ends`
more than INACTIVE_DAYS in the past, and the demotion job has actually tagged
the user as sitting in FREE. Requiring the tag as well as the date is what
keeps this from racing the job that owns the squad -- someone it has not
reached yet is left for the next pass.

Our own `users` row is kept. It is what stops a returning user being handed a
second trial: eligibility is "has never had a subscription", judged on
`subscription_ends`, not on whether a panel account exists.
"""

import logging
import time

from app.notify.admin import send_admin_message
from app.services.users import user_service
from tgvpn_shared.db import UserRepository
from tgvpn_shared.remnawave.client import panel_ref
from tgvpn_shared.settings import get_settings

logger = logging.getLogger(__name__)
_users_repo = UserRepository()

INACTIVE_DAYS = 30
ERROR_THROTTLE_SECONDS = 3600
_last_error_ts: float | None = None


async def resolve_panel_uuid(row: dict) -> str | None:
    """
    Find this user's panel account.

    By stored UUID first. Looking up `str(telegram_id)` alone -- which is all
    this did before the identity rework -- would miss every account created
    since, because those are named `u-<uuid>` and would quietly never be
    cleaned up at all.
    """
    if row.get("remnawave_uuid"):
        return str(row["remnawave_uuid"])

    telegram_id = row.get("telegram_id")
    candidates = [
        row.get("remnawave_username"),
        str(telegram_id) if telegram_id is not None else None,
    ]
    for name in candidates:
        if not name:
            continue
        found = await user_service.get_user_by_username(name)
        # `panel_ref`: a newer panel answers with a numeric `id` and no `uuid`,
        # and reading that key alone found nothing to delete on such a panel.
        if found and panel_ref(found):
            return panel_ref(found)
    return None


async def run_inactive_user_cleanup() -> None:
    """Delete the panel accounts of users who stopped paying a month ago."""
    settings = get_settings()
    deleted = 0
    skipped = 0
    failures: list[str] = []

    try:
        inactive = await _users_repo.get_inactive_users_for_cleanup(
            INACTIVE_DAYS, free_tier_enabled=settings.free_tier_enabled
        )
        if not inactive:
            logger.info("Inactive cleanup: no users to process.")
            return

        for row in inactive:
            label = row.get("telegram_id") or row.get("id")
            try:
                user_uuid = await resolve_panel_uuid(row)
                if not user_uuid:
                    # Already gone from the panel. Clear the dead handles so
                    # the next lookup does not chase them again.
                    if row.get("id"):
                        await _users_repo.clear_panel_identity(str(row["id"]))
                    skipped += 1
                    continue

                await user_service.delete_user(user_uuid)
                if row.get("id"):
                    await _users_repo.clear_panel_identity(str(row["id"]))
                deleted += 1
            except Exception as exc:
                failures.append(f"{label}: {exc}")
                logger.warning("Inactive cleanup failed for %s: %s", label, exc)

        if deleted or failures:
            mode = "free-squad" if settings.free_tier_enabled else "expired"
            lines = [
                "🧹 Очистка неактивных пользователей Remnawave",
                f"Порог: {INACTIVE_DAYS} дней без оплаты ({mode})",
                f"Удалено: {deleted}",
                f"Уже отсутствовали в Remnawave: {skipped}",
                f"Ошибок: {len(failures)}",
            ]
            if failures:
                preview = failures[:10]
                lines.append("Примеры ошибок:")
                lines.extend([f"• {item}" for item in preview])
                if len(failures) > len(preview):
                    lines.append(f"… и ещё {len(failures) - len(preview)}")
            await send_admin_message("\n".join(lines))
    except Exception as exc:
        logger.error("Inactive cleanup failed: %s", exc, exc_info=True)
        now = time.time()
        global _last_error_ts
        if _last_error_ts is None or now - _last_error_ts >= ERROR_THROTTLE_SECONDS:
            await send_admin_message(
                "❌ Ошибка очистки неактивных пользователей.\n"
                f"Причина: {exc}"
            )
            _last_error_ts = now

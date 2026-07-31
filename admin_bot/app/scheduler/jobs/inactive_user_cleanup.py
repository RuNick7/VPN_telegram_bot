"""Cleanup Remnawave users inactive for a month."""

import logging
import time

from app.notify.admin import send_admin_message
from app.services.users import user_service
from tgvpn_shared.db import UserRepository
from tgvpn_shared.settings import get_settings

logger = logging.getLogger(__name__)
_users_repo = UserRepository()

INACTIVE_DAYS = 30
ERROR_THROTTLE_SECONDS = 3600
_last_error_ts: float | None = None


async def run_inactive_user_cleanup() -> None:
    """
    Delete Remnawave users inactive for INACTIVE_DAYS.

    Our own `users` rows are kept, which is what stops a returning user being
    handed a second trial: eligibility is judged on `subscription_ends` having
    never been set, not on whether a panel account exists.

    Skipped entirely when the FREE tier is on. The two features want opposite
    things -- FREE tier keeps a lapsed account alive so it falls back to the
    free servers, and deleting it is precisely what that is meant to prevent.
    """
    if get_settings().free_tier_enabled:
        logger.info("Inactive cleanup skipped: the FREE tier keeps lapsed accounts alive.")
        return

    deleted = 0
    skipped = 0
    failures: list[str] = []
    try:
        inactive = await _users_repo.get_inactive_users_for_cleanup(INACTIVE_DAYS)
        if not inactive:
            logger.info("Inactive cleanup: no users to process.")
            return

        for row in inactive:
            telegram_id = row["telegram_id"]
            # Resolve by stored UUID first. Looking up `str(telegram_id)` alone
            # would miss every account created after the identity rework --
            # those are named `u-<uuid>` and would quietly never be cleaned up.
            try:
                user_uuid = row.get("remnawave_uuid")
                if not user_uuid:
                    for name in (row.get("remnawave_username"), str(telegram_id) if telegram_id else None):
                        if not name:
                            continue
                        found = await user_service.get_user_by_username(name)
                        if found and found.get("uuid"):
                            user_uuid = found["uuid"]
                            break
                if not user_uuid:
                    skipped += 1
                    continue
                await user_service.delete_user(str(user_uuid))
                deleted += 1
            except Exception as exc:
                failures.append(f"{telegram_id}: {exc}")
                logger.warning("Inactive cleanup failed for %s: %s", telegram_id, exc)

        if deleted or failures:
            lines = [
                "🧹 Очистка неактивных пользователей Remnawave",
                f"Порог: {INACTIVE_DAYS} дней без активной подписки",
                f"Удалено: {deleted}",
                f"Не найдено в Remnawave: {skipped}",
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

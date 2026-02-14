"""Cleanup Remnawave users inactive for a month."""

import logging
import time

from app.notify.admin import send_admin_message
from app.services.subscription_db import get_inactive_telegram_ids_for_cleanup
from app.services.users import user_service

logger = logging.getLogger(__name__)

INACTIVE_DAYS = 30
ERROR_THROTTLE_SECONDS = 3600
_last_error_ts: float | None = None


async def run_inactive_user_cleanup() -> None:
    """
    Delete Remnawave users inactive for INACTIVE_DAYS.

    User rows remain in subscription.db to prevent re-issuing trial access.
    """
    deleted = 0
    skipped = 0
    failures: list[str] = []
    try:
        inactive_ids = await get_inactive_telegram_ids_for_cleanup(INACTIVE_DAYS)
        if not inactive_ids:
            logger.info("Inactive cleanup: no users to process.")
            return

        for telegram_id in inactive_ids:
            username = str(telegram_id)
            try:
                user = await user_service.get_user_by_username(username)
                user_uuid = user.get("uuid")
                if not user_uuid:
                    skipped += 1
                    continue
                await user_service.delete_user(user_uuid)
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

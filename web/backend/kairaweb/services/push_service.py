"""Web Push (VAPID) sender.

Wraps `pywebpush` to deliver notifications to all subscriptions of a user.
Automatically prunes dead subscriptions (gone/expired endpoints).

This module is sync. Callers must invoke it through ``asyncio.to_thread``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from kairaweb.core.settings import get_settings
from kairaweb.core.storage import (
    delete_push_subscription_by_endpoint,
    list_push_subscriptions,
    touch_push_subscription,
)


logger = logging.getLogger(__name__)


def _is_dead_status(status: int) -> bool:
    return status in (404, 410)


def _send_one(*, subscription_info: dict[str, Any], data: dict[str, Any]) -> bool:
    """Send a single push. Returns True on success, False otherwise."""
    settings = get_settings()
    if not (settings.vapid_private_key and settings.vapid_contact):
        logger.warning("push: VAPID is not configured; skipping send")
        return False

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.error("push: pywebpush is not installed; run pip install pywebpush")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(data, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_contact},
            ttl=60 * 60 * 24,
        )
        touch_push_subscription(subscription_info["endpoint"])
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None) if exc.response else None
        if status and _is_dead_status(status):
            delete_push_subscription_by_endpoint(subscription_info["endpoint"])
            logger.info("push: pruned dead subscription %s (status=%s)", subscription_info["endpoint"], status)
        else:
            logger.warning("push: send failed status=%s detail=%s", status, exc)
        return False
    except Exception:
        logger.exception("push: unexpected error while sending")
        return False


def send_to_user(
    telegram_id: int,
    *,
    title: str,
    body: str,
    url: str | None = None,
    tag: str | None = None,
    data: dict[str, Any] | None = None,
) -> int:
    """Sync. Send a push to all subscriptions of a single user. Returns count delivered."""
    payload = {
        "title": title,
        "body": body,
        "url": url or "/cabinet",
        "tag": tag or "kaira-default",
        "data": data or {},
    }

    delivered = 0
    for sub in list_push_subscriptions(int(telegram_id)):
        info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        if _send_one(subscription_info=info, data=payload):
            delivered += 1
    return delivered


def send_to_users(
    telegram_ids: Iterable[int],
    *,
    title: str,
    body: str,
    url: str | None = None,
    tag: str | None = None,
    data: dict[str, Any] | None = None,
) -> int:
    delivered = 0
    seen: set[int] = set()
    for tid in telegram_ids:
        if int(tid) in seen:
            continue
        seen.add(int(tid))
        delivered += send_to_user(
            int(tid), title=title, body=body, url=url, tag=tag, data=data
        )
    return delivered

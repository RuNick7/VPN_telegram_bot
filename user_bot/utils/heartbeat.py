"""
Liveness heartbeat for user_bot.

A wedged event loop is invisible from outside: the process is running, the
container is healthy, Telegram's API is reachable — and nobody is being
served. Touching a file from inside the loop makes that state observable,
because a blocked loop stops touching it.

admin_bot's `service_health_monitor` reads the file's mtime and alerts when it
goes stale.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from tgvpn_shared.settings import get_settings

logger = logging.getLogger(__name__)

# Well under the monitor's staleness threshold, so an alert means the loop
# really is stuck rather than that we happened to write late.
BEAT_INTERVAL_SECONDS = 60


def touch_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


async def heartbeat_loop() -> None:
    """Touch the heartbeat file until cancelled."""
    path = Path(get_settings().user_bot_heartbeat_path)
    logger.info("Heartbeat writing to %s every %ss", path, BEAT_INTERVAL_SECONDS)
    while True:
        try:
            touch_heartbeat(path)
        except Exception as exc:
            # An unwritable heartbeat path must not take the bot down -- it
            # only costs us the liveness signal.
            logger.warning("Could not write heartbeat to %s: %s", path, exc)
        await asyncio.sleep(BEAT_INTERVAL_SECONDS)

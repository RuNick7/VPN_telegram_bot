"""
Test bootstrap for user_bot.

user_bot's modules import each other with absolute names (`from bot import bot`,
`from handlers import ...`, ...) that only resolve when user_bot/ itself is on
sys.path — that's how the bot processes are normally launched. Tests need the
same layout, and a few modules read required env vars at import time (e.g.
bot.py constructs a real aiogram Bot from USER_BOT_TOKEN), so both have to be
set up before any user_bot module is imported.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("USER_BOT_TOKEN", "123456789:TEST-0000000000000000000000000")
os.environ.setdefault("ADMIN_IDS", "")
# Tests run on the host, outside docker-compose's network, so they hit the
# published host port (5433) rather than the `postgres` hostname the bots use
# inside the compose network. Repository calls are mocked in the security
# tests, but module import touches this module-level constant regardless.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://tgvpn:tgvpn_local_dev_only@127.0.0.1:5433/tgvpn",
)
os.environ.setdefault("YOOKASSA_SHOP_ID", "test-shop-id")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test-secret-key")

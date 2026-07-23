"""
Test bootstrap for user_bot.

user_bot's modules import each other with absolute names (`from bot import bot`,
`from data import db_utils`, ...) that only resolve when user_bot/ itself is on
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
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("YOOKASSA_SHOP_ID", "test-shop-id")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test-secret-key")

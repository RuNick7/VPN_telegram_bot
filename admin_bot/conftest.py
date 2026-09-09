"""
Test bootstrap for admin_bot -- mirrors user_bot/conftest.py. admin_bot's
modules use absolute imports (`from app.config.settings import settings`,
...) that only resolve when admin_bot/ itself is on sys.path, and several
modules construct real objects (pydantic Settings, RemnawaveClient) at import
time that require env vars to be set first.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("Admin_bot_token", "123456789:TEST-0000000000000000000000000")
os.environ.setdefault("ADMIN_IDS", "111111111")
os.environ.setdefault("REMNAWAVE_BASE_URL", "https://remnawave.test.invalid")
os.environ.setdefault("REMNAWAVE_TOKEN", "test-token")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://tgvpn:tgvpn_local_dev_only@127.0.0.1:5433/tgvpn",
)

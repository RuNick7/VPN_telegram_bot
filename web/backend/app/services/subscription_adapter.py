import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class SubscriptionAdapterError(RuntimeError):
    pass


class SubscriptionServiceAdapter:
    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[4]
        self._user_bot_root = self._repo_root / "user_bot"

    def get_subscription_snapshot(self, telegram_id: int) -> dict[str, Any]:
        payload = self._run_user_bot_op(
            "get_subscription_snapshot",
            {"telegram_id": int(telegram_id)},
        )

        now_ts = int(time.time())
        expire_at = int(payload.get("expire_at", 0) or 0)
        return {
            "telegram_id": int(telegram_id),
            "subscription_ends": int(payload.get("subscription_ends", 0) or 0),
            "expire_at": expire_at,
            "is_active": expire_at > now_ts,
            "subscription_url": payload.get("subscription_url") or "",
            "panel_user_exists": bool(payload.get("panel_user_exists", True)),
            "source": "user_bot_adapter",
        }

    def _run_user_bot_op(self, operation: str, args: dict[str, Any]) -> dict[str, Any]:
        script = """
import json
import sys
from pathlib import Path

op = sys.argv[1]
args = json.loads(sys.argv[2])
user_bot_root = Path(sys.argv[3])
sys.path.insert(0, str(user_bot_root))

from app.services.remnawave import vpn_service
from data import db_utils

if op == "get_subscription_snapshot":
    telegram_id = int(args["telegram_id"])
    username = str(telegram_id)
    user = db_utils.get_user_by_id(telegram_id)
    subscription_ends = int(user["subscription_ends"]) if user and user["subscription_ends"] else 0

    try:
        token = vpn_service.get_token(telegram_id)
        expire_at = int(vpn_service.get_user_expire(username, token))
        subscription_url = vpn_service.get_subscription_url(username, token)
        panel_user_exists = True
    except ValueError as exc:
        if "User not found" not in str(exc):
            raise
        expire_at = 0
        subscription_url = ""
        panel_user_exists = False

    print(json.dumps({
        "subscription_ends": subscription_ends,
        "expire_at": expire_at,
        "subscription_url": subscription_url,
        "panel_user_exists": panel_user_exists,
    }))
else:
    raise ValueError(f"Unsupported operation: {op}")
"""
        result = subprocess.run(
            [sys.executable, "-c", script, operation, json.dumps(args), str(self._user_bot_root)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self._repo_root),
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            if err:
                err = err.splitlines()[-1]
            raise SubscriptionAdapterError(err or "User bot adapter failed.")

        try:
            return json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError as exc:
            raise SubscriptionAdapterError("User bot adapter returned invalid JSON.") from exc

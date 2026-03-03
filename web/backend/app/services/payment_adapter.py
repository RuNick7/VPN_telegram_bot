import ipaddress
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class PaymentAdapterError(RuntimeError):
    pass


class PaymentServiceAdapter:
    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[4]
        self._user_bot_root = self._repo_root / "user_bot"

    def create_subscription_payment(
        self,
        *,
        telegram_id: int,
        months: int,
        return_url: str,
    ) -> dict[str, Any]:
        return self._run_user_bot_op(
            "create_subscription_payment",
            {
                "telegram_id": int(telegram_id),
                "months": int(months),
                "return_url": return_url,
            },
        )

    def fetch_payment(self, *, payment_id: str) -> dict[str, Any]:
        return self._run_user_bot_op(
            "fetch_payment",
            {"payment_id": payment_id},
        )

    def process_webhook_success(self, *, payment_id: str) -> dict[str, Any]:
        return self._run_user_bot_op(
            "process_webhook_success",
            {"payment_id": payment_id},
        )

    def is_allowed_source(self, request_ip: str | None) -> bool:
        allowed = (os.getenv("YOOKASSA_WEBHOOK_ALLOWED_CIDRS") or "").strip()
        if not allowed:
            return True
        if not request_ip:
            return False
        try:
            ip_addr = ipaddress.ip_address(request_ip)
        except ValueError:
            return False
        cidrs = [c.strip() for c in allowed.split(",") if c.strip()]
        if not cidrs:
            return True
        for cidr in cidrs:
            try:
                if ip_addr in ipaddress.ip_network(cidr, strict=False):
                    return True
            except ValueError:
                logger.warning("Invalid CIDR in YOOKASSA_WEBHOOK_ALLOWED_CIDRS: %s", cidr)
        return False

    def is_valid_webhook_secret(self, header_secret: str | None) -> bool:
        expected = (os.getenv("YOOKASSA_WEBHOOK_SECRET") or "").strip()
        if not expected:
            return True
        return bool(header_secret) and header_secret == expected

    def _run_user_bot_op(self, operation: str, args: dict[str, Any]) -> dict[str, Any]:
        script = """
import json
import sys
from pathlib import Path

op = sys.argv[1]
args = json.loads(sys.argv[2])
user_bot_root = Path(sys.argv[3])
sys.path.insert(0, str(user_bot_root))

from data import db_utils
from handlers.utils import get_subscription_price
from payments.yookassa_client import create_payment, fetch_payment
from app.services.remnawave.vpn_service import extend_subscription_by_telegram_id

if op == "create_subscription_payment":
    telegram_id = int(args["telegram_id"])
    months = int(args["months"])
    if months not in (1, 3, 6, 12):
        raise ValueError("Unsupported months value")
    user = db_utils.get_user_by_id(telegram_id)
    referred_people = int(user["referred_people"]) if user else 0
    amount = get_subscription_price(months, referred_people)
    days_to_extend = months * 30
    description = f"Оплата подписки на {months} мес."
    payment = create_payment(
        amount=amount,
        description=description,
        return_url=args["return_url"],
        telegram_id=telegram_id,
        days_to_extend=days_to_extend,
    )
    payment_id = str(payment.id)
    db_utils.update_payment_status(payment_id, str(payment.status))
    print(json.dumps({
        "payment_id": payment_id,
        "status": str(payment.status),
        "confirmation_url": str(payment.confirmation.confirmation_url),
        "amount": float(amount),
        "days_to_extend": days_to_extend,
    }))
elif op == "fetch_payment":
    payment_id = str(args["payment_id"])
    local_status = db_utils.get_payment_status(payment_id)
    payment = fetch_payment(payment_id)
    metadata = getattr(payment, "metadata", None) or {}
    confirmation = getattr(payment, "confirmation", None)
    confirmation_url = getattr(confirmation, "confirmation_url", None) if confirmation else None
    print(json.dumps({
        "payment_id": payment_id,
        "status": str(getattr(payment, "status", "") or ""),
        "local_status": str(local_status or ""),
        "metadata": {
            "telegram_id": metadata.get("telegram_id"),
            "days_to_extend": metadata.get("days_to_extend"),
            "is_gift": metadata.get("is_gift"),
        },
        "confirmation_url": confirmation_url,
    }))
elif op == "process_webhook_success":
    payment_id = str(args["payment_id"])
    if db_utils.get_payment_status(payment_id) == "succeeded":
        print(json.dumps({"ok": True, "idempotent": True, "status": "succeeded"}))
    else:
        payment = fetch_payment(payment_id)
        payment_status = str(getattr(payment, "status", "") or "")
        if payment_status != "succeeded":
            db_utils.update_payment_status(payment_id, payment_status or "unknown")
            print(json.dumps({"ok": True, "idempotent": False, "status": payment_status or "unknown"}))
        else:
            metadata = getattr(payment, "metadata", None) or {}
            telegram_id = metadata.get("telegram_id")
            days_to_extend = metadata.get("days_to_extend", 30)
            if telegram_id is None:
                raise ValueError("Missing telegram_id in payment metadata")
            try:
                telegram_id = int(telegram_id)
                days_to_extend = int(days_to_extend)
            except (TypeError, ValueError):
                raise ValueError("Invalid payment metadata values")
            if days_to_extend <= 0:
                days_to_extend = 30
            result = extend_subscription_by_telegram_id(telegram_id, days_to_extend)
            if isinstance(result, str) and result.startswith("❌"):
                db_utils.update_payment_status(payment_id, "processing_error")
                raise ValueError(result)
            db_utils.update_payment_status(payment_id, "succeeded")
            print(json.dumps({
                "ok": True,
                "idempotent": False,
                "status": "succeeded",
                "telegram_id": telegram_id,
                "days_to_extend": days_to_extend,
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
            raise PaymentAdapterError(err or "Payment adapter failed.")
        try:
            return json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError as exc:
            raise PaymentAdapterError("Payment adapter returned invalid JSON.") from exc

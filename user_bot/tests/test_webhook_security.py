"""
Regression test for the YooKassa webhook payment-forgery fix.

The webhook has no signature/secret of its own — the only trustworthy source
of a payment's status is a direct fetch back from YooKassa's API by payment_id.
Before the fix, a failed fetch (guaranteed for a forged/nonexistent payment_id)
fell through to processing the raw, unauthenticated request body instead of
aborting, letting anyone who knew the webhook URL forge free subscription
extensions or gift codes.
"""

from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import payments.webhook as webhook_module


class _FakeYooKassaError(Exception):
    pass


def _raise_not_found(payment_id):
    raise _FakeYooKassaError(f"payment {payment_id} not found")


async def test_forged_payment_is_rejected_when_verification_fails(monkeypatch):
    monkeypatch.setattr(webhook_module, "fetch_payment", _raise_not_found)

    claim_mock = AsyncMock()
    monkeypatch.setattr(webhook_module._payments, "claim_payment_processing", claim_mock)

    app = web.Application()
    app.router.add_post("/webhook-yookassa", webhook_module.yookassa_webhook_handler)

    forged_payload = {
        "event": "payment.succeeded",
        "object": {
            "id": "forged-payment-id-does-not-exist",
            "status": "succeeded",
            "metadata": {
                "telegram_id": 999999999,
                "days_to_extend": 3650,
                "is_gift": "false",
            },
        },
    }

    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/webhook-yookassa", json=forged_payload)
        # The handler must refuse the request outright...
        assert resp.status in (502, 504)

    # ...and must never even attempt to claim/credit an unverified payment.
    claim_mock.assert_not_called()


async def test_real_payment_id_with_forged_event_but_unpaid_status_is_ignored(monkeypatch):
    """
    Guards the second half of the bug: even when the fetch succeeds, a payment
    whose *verified* status isn't "succeeded" must not be credited just
    because the request body's `event` field claims "payment.succeeded".
    """

    class _PendingPayment:
        status = "pending"
        metadata = {"telegram_id": 999999999, "days_to_extend": 3650, "is_gift": "false"}

    monkeypatch.setattr(webhook_module, "fetch_payment", lambda payment_id: _PendingPayment())

    claim_mock = AsyncMock()
    monkeypatch.setattr(webhook_module._payments, "claim_payment_processing", claim_mock)

    app = web.Application()
    app.router.add_post("/webhook-yookassa", webhook_module.yookassa_webhook_handler)

    forged_payload = {
        "event": "payment.succeeded",  # forged: real payment is still "pending"
        "object": {
            "id": "real-but-unpaid-payment-id",
            "status": "succeeded",  # forged: doesn't match the verified fetch
            "metadata": {"telegram_id": 999999999, "days_to_extend": 3650, "is_gift": "false"},
        },
    }

    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/webhook-yookassa", json=forged_payload)
        assert resp.status == 200

    claim_mock.assert_not_called()

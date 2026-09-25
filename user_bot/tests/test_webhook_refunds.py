"""
Notifications that are not about a payment.

`WebhookNotification` builds its `object` as a PaymentResponse whatever the
event is, so `object.id` for a refund is the *refund's* id. Feeding that to
`fetch_payment` asks YooKassa for a payment that does not exist, and the answer
-- "Incorrect payment_id. Payment doesn't exist or access denied" -- is
indistinguishable from a forged payment id. So a refund produced an admin alert
about a broken payment and a 502, which is YooKassa's cue to deliver it again,
and again, for as long as it kept retrying.
"""

from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import payments.webhook as webhook

REFUND_ID = "322f4253-0015-5001-8000-115b0ffa8b63"
PAYMENT_ID = "2e7dcb31-0000-5000-9000-1e5b0ffa8b63"


class _Amount:
    value = "299.00"
    currency = "RUB"


class _Refund:
    id = REFUND_ID
    payment_id = PAYMENT_ID
    status = "succeeded"
    amount = _Amount()


def refund_payload(event: str = "refund.succeeded") -> dict:
    return {
        "type": "notification",
        "event": event,
        "object": {"id": REFUND_ID, "status": "succeeded", "amount": {"value": "299.00",
                                                                     "currency": "RUB"}},
    }


@pytest.fixture
def webhook_client(monkeypatch):
    """The endpoint, with every outward call replaced by a recording double."""
    sent: list[str] = []
    fetched_payments: list[str] = []

    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append(text))
    monkeypatch.setattr(webhook, "bot", bot)
    monkeypatch.setattr(webhook, "ADMIN_ID", 4242)

    def record_payment_fetch(payment_id):
        fetched_payments.append(payment_id)
        raise AssertionError(f"fetch_payment should not be reached for {payment_id}")

    monkeypatch.setattr(webhook, "fetch_payment", record_payment_fetch)
    monkeypatch.setattr(webhook._payments, "claim_payment_processing", AsyncMock())

    app = web.Application()
    app.router.add_post("/webhook-yookassa", webhook.yookassa_webhook_handler)
    return app, sent, fetched_payments


async def post(app, payload):
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/webhook-yookassa", json=payload)
        return response.status


# -- refunds ---------------------------------------------------------------


async def test_a_refund_is_not_mistaken_for_a_broken_payment(monkeypatch, webhook_client):
    """
    The regression. 502 is what made this repeat: YooKassa treats it as "not
    delivered" and sends the same notification again.
    """
    app, sent, fetched_payments = webhook_client
    monkeypatch.setattr(webhook, "fetch_refund", lambda refund_id: _Refund())
    monkeypatch.setattr(webhook, "_refund_payer_label", AsyncMock(return_value="@someone"))

    assert await post(app, refund_payload()) == 200
    assert fetched_payments == []
    assert not any("YooKassa API error" in message for message in sent)


async def test_a_refund_never_claims_the_payment(monkeypatch, webhook_client):
    """Nothing is credited, and nothing is marked as being credited."""
    app, _sent, _fetched = webhook_client
    monkeypatch.setattr(webhook, "fetch_refund", lambda refund_id: _Refund())
    monkeypatch.setattr(webhook, "_refund_payer_label", AsyncMock(return_value="—"))

    await post(app, refund_payload())

    webhook._payments.claim_payment_processing.assert_not_awaited()


async def test_the_alert_names_the_payment_not_the_refund(monkeypatch, webhook_client):
    """
    An operator deciding whether to revoke access needs the id they can find in
    their own records, and that is the payment's.
    """
    app, sent, _fetched = webhook_client
    monkeypatch.setattr(webhook, "fetch_refund", lambda refund_id: _Refund())
    monkeypatch.setattr(webhook, "_refund_payer_label", AsyncMock(return_value="@someone"))

    await post(app, refund_payload())

    assert len(sent) == 1
    assert PAYMENT_ID in sent[0]
    assert "299.00 RUB" in sent[0]
    assert "@someone" in sent[0]


async def test_an_unverifiable_refund_says_nothing(monkeypatch, webhook_client):
    """
    The alert is built from a verified reading or not at all: one assembled
    from the request body is a way to talk an operator into cutting off a
    customer who never got their money back.
    """
    app, sent, _fetched = webhook_client

    def refuse(refund_id):
        raise RuntimeError("not found")

    monkeypatch.setattr(webhook, "fetch_refund", refuse)

    assert await post(app, refund_payload()) == 200
    assert sent == []


async def test_a_refund_that_has_not_gone_through_says_nothing(monkeypatch, webhook_client):
    app, sent, _fetched = webhook_client

    class _Pending(_Refund):
        status = "pending"

    monkeypatch.setattr(webhook, "fetch_refund", lambda refund_id: _Pending())

    assert await post(app, refund_payload()) == 200
    assert sent == []


# -- everything else YooKassa sends ----------------------------------------


@pytest.mark.parametrize("event", ["deal.closed", "payout.succeeded", "payout.canceled"])
async def test_other_objects_are_acknowledged_and_dropped(event, webhook_client):
    """
    Their `object.id` is a deal or payout id and would 404 the same way. 200,
    because a 502 asks for a redelivery of something there is nothing to do
    with.
    """
    app, sent, fetched_payments = webhook_client

    assert await post(app, {"type": "notification", "event": event,
                            "object": {"id": "some-other-id"}}) == 200
    assert fetched_payments == []
    assert sent == []


async def test_payment_events_still_go_through_verification(monkeypatch, webhook_client):
    """
    The filter must not have swallowed the path it was added beside. A payment
    notification is still verified against YooKassa before anything happens.
    """
    app, _sent, _fetched = webhook_client
    seen: list[str] = []

    def fetch(payment_id):
        seen.append(payment_id)
        raise RuntimeError("upstream down")

    monkeypatch.setattr(webhook, "fetch_payment", fetch)

    status = await post(app, {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {"id": PAYMENT_ID, "status": "succeeded", "metadata": {}},
    })

    assert seen == [PAYMENT_ID]
    assert status == 502

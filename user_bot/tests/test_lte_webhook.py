"""
Traffic purchases through the payment webhook.

The Phase 0 rule still governs everything here: metadata is only ever read
back from a *verified* server-to-server fetch, never from the callback body.
These tests cover what the verified metadata is then used for -- crediting
gigabytes instead of extending a subscription.
"""

from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import payments.webhook as webhook_module

TELEGRAM_ID = 555
GB = 1024**3


class _SucceededPayment:
    """A verified YooKassa payment, as `fetch_payment` would return it."""

    status = "succeeded"

    def __init__(self, **metadata):
        self.metadata = {"telegram_id": TELEGRAM_ID, **metadata}


def _app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook-yookassa", webhook_module.yookassa_webhook_handler)
    return app


def _body(**metadata) -> dict:
    return {
        "event": "payment.succeeded",
        "object": {"id": "pay-1", "status": "succeeded", "metadata": metadata},
    }


@pytest.fixture
def wired(monkeypatch):
    """Stub every side effect so only the branching logic is under test."""
    monkeypatch.setattr(webhook_module._payments, "claim_payment_processing", AsyncMock(return_value=True))
    monkeypatch.setattr(webhook_module._payments, "update_payment_status", AsyncMock())
    monkeypatch.setattr(webhook_module, "_send_markdown_or_plain", AsyncMock())

    credit = AsyncMock(return_value=15 * GB)
    extend = AsyncMock(return_value="✅ продлено")
    award = AsyncMock(return_value=True)
    monkeypatch.setattr(webhook_module._lte, "credit_balance", credit)
    monkeypatch.setattr(webhook_module, "extend_subscription", extend)
    monkeypatch.setattr(webhook_module._users, "get_user_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr(webhook_module._users, "award_referral", award)
    return {"credit": credit, "extend": extend, "award": award}


async def _post(payload: dict) -> int:
    async with TestClient(TestServer(_app())) as client:
        response = await client.post("/webhook-yookassa", json=payload)
        return response.status


async def test_a_traffic_purchase_credits_gigabytes(wired, monkeypatch):
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(lte_gb="10", days_to_extend="0")
    )

    assert await _post(_body(lte_gb="10")) == 200
    wired["credit"].assert_awaited_once_with(TELEGRAM_ID, 10 * GB)


async def test_a_traffic_purchase_does_not_extend_the_subscription(wired, monkeypatch):
    """Buying traffic must not silently add subscription days."""
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(lte_gb="10", days_to_extend="0")
    )

    await _post(_body(lte_gb="10"))
    wired["extend"].assert_not_awaited()


async def test_a_traffic_purchase_awards_no_referral_bonus(wired, monkeypatch):
    """
    The referral programme covers subscriptions only.

    Otherwise a cheap traffic pack would trigger the same referrer payout as a
    year of subscription.
    """
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(lte_gb="5", days_to_extend="0")
    )

    await _post(_body(lte_gb="5"))
    wired["award"].assert_not_awaited()


async def test_a_subscription_payment_still_extends(wired, monkeypatch):
    """The traffic branch must not have swallowed the ordinary path."""
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(days_to_extend="30")
    )

    assert await _post(_body(days_to_extend="30")) == 200
    wired["extend"].assert_awaited_once_with(TELEGRAM_ID, 30)
    wired["credit"].assert_not_awaited()


@pytest.mark.parametrize("value", ["0", "", None, "abc"])
async def test_a_non_traffic_marker_falls_through_to_subscription(wired, monkeypatch, value):
    monkeypatch.setattr(
        webhook_module,
        "fetch_payment",
        lambda _id: _SucceededPayment(lte_gb=value, days_to_extend="30"),
    )

    await _post(_body(days_to_extend="30"))
    wired["extend"].assert_awaited_once()
    wired["credit"].assert_not_awaited()


async def test_zero_days_is_not_rewritten_to_30_for_a_traffic_purchase(wired, monkeypatch):
    """
    A traffic purchase legitimately sends 0 days.

    The subscription path treats 0 as "value lost" and substitutes 30; letting
    that apply here would hand out a free month with every traffic pack.
    """
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(lte_gb="10", days_to_extend="0")
    )

    await _post(_body(lte_gb="10"))
    wired["extend"].assert_not_awaited()


async def test_a_failed_credit_marks_the_payment_for_retry(wired, monkeypatch):
    """
    Mirrors the subscription-failure path: a paid-for-but-uncredited purchase
    must be reclaimable, not recorded as done.
    """
    monkeypatch.setattr(
        webhook_module, "fetch_payment", lambda _id: _SucceededPayment(lte_gb="10", days_to_extend="0")
    )
    monkeypatch.setattr(webhook_module._lte, "credit_balance", AsyncMock(return_value=None))

    assert await _post(_body(lte_gb="10")) == 200
    statuses = [call.args[1] for call in webhook_module._payments.update_payment_status.await_args_list]
    assert "processing_error" in statuses


async def test_an_unverified_traffic_purchase_credits_nothing(wired, monkeypatch):
    """
    The Phase 0 guarantee, restated for this path: a forged callback whose
    payment cannot be verified must not credit traffic.
    """

    def _fail(_payment_id):
        raise RuntimeError("payment not found")

    monkeypatch.setattr(webhook_module, "fetch_payment", _fail)

    assert await _post(_body(lte_gb="30")) in (502, 504)
    wired["credit"].assert_not_awaited()

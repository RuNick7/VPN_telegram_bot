import asyncio

import pytest

from tgvpn_shared.db import PaymentRepository


@pytest.fixture
def payments() -> PaymentRepository:
    return PaymentRepository()


async def test_claim_payment_processing_blocks_concurrent_double_claim(payments: PaymentRepository):
    """The core guarantee webhook.py relies on: two concurrent claims for the
    same payment_id must not both succeed."""
    results = await asyncio.gather(
        payments.claim_payment_processing("pay-1"),
        payments.claim_payment_processing("pay-1"),
    )
    assert sorted(results) == [False, True]


async def test_claim_payment_processing_rejects_already_succeeded(payments: PaymentRepository):
    await payments.claim_payment_processing("pay-2")
    await payments.update_payment_status("pay-2", "succeeded")

    claimed_again = await payments.claim_payment_processing("pay-2")

    assert claimed_again is False


async def test_claim_payment_processing_allows_reclaim_after_stale_window(payments: PaymentRepository):
    await payments.claim_payment_processing("pay-3", stale_seconds=0)

    # stale_seconds=0 means "processing" claims are immediately reclaimable,
    # simulating a crash mid-processing that must not block retries forever.
    reclaimed = await payments.claim_payment_processing("pay-3", stale_seconds=0)

    assert reclaimed is True


async def test_update_payment_status_upserts(payments: PaymentRepository):
    assert await payments.get_payment_status("pay-4") is None

    await payments.update_payment_status("pay-4", "succeeded")

    assert await payments.get_payment_status("pay-4") == "succeeded"

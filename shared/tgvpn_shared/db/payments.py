"""Repository for the `payments` table — replaces the payment functions in
user_bot/data/db_utils.py."""

from __future__ import annotations

from .pool import get_pool


class PaymentRepository:
    async def update_payment_status(self, payment_id: str, new_status: str) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO payments (payment_id, status, created_at, updated_at)
            VALUES ($1, $2, now(), now())
            ON CONFLICT (payment_id) DO UPDATE
            SET status = EXCLUDED.status, updated_at = now()
            """,
            payment_id, new_status,
        )

    async def get_payment_status(self, payment_id: str) -> str | None:
        pool = await get_pool()
        return await pool.fetchval(
            "SELECT status FROM payments WHERE payment_id = $1", payment_id
        )

    async def claim_payment_processing(self, payment_id: str, stale_seconds: int = 600) -> bool:
        """
        Atomically claims a payment for processing (status='processing').

        Returns False if the payment is already 'succeeded' or is currently
        being processed by another webhook delivery — guards against
        double-crediting on YooKassa retries/races. A 'processing' claim
        older than stale_seconds is reclaimable, so a crash mid-processing
        doesn't block retries forever.
        """
        pool = await get_pool()
        claimed = await pool.fetchval(
            """
            INSERT INTO payments (payment_id, status, created_at, updated_at)
            VALUES ($1, 'processing', now(), now())
            ON CONFLICT (payment_id) DO UPDATE
            SET status = 'processing', updated_at = now()
            WHERE payments.status != 'succeeded'
              AND (payments.status != 'processing' OR payments.updated_at < now() - ($2 * INTERVAL '1 second'))
            RETURNING payment_id
            """,
            payment_id, stale_seconds,
        )
        return claimed is not None

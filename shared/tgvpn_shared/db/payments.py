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

    async def unsettled(self, limit: int = 20) -> list:
        """
        Payments that never reached `succeeded`, newest first.

        This is the list nobody could see. A row stuck in `processing_error`
        means somebody paid and was not credited, and until the payment knew
        whose it was, finding out meant reading the YooKassa dashboard and
        matching timestamps by hand -- which is why one sat unnoticed for a
        day.

        `pending` rows younger than a few minutes are ordinary: the customer is
        still on the payment page. Filtering is left to the caller so the
        window is a UI decision rather than one baked in here.
        """
        pool = await get_pool()
        return await pool.fetch(
            """
            SELECT
                p.payment_id,
                p.status,
                p.purpose,
                p.days,
                EXTRACT(EPOCH FROM p.created_at)::bigint AS created_at,
                EXTRACT(EPOCH FROM p.updated_at)::bigint AS updated_at,
                u.telegram_id,
                u.telegram_tag,
                u.email
            FROM payments p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.status <> 'succeeded'
            ORDER BY p.updated_at DESC
            LIMIT $1
            """,
            limit,
        )

    async def record_intent(
        self, payment_id: str, user_id: str | None, purpose: str, days: int
    ) -> None:
        """
        Record what a payment was for, at the moment it is created.

        Deliberately does not touch `status`. That column belongs to the
        webhook and only to it, because only the webhook re-fetches the payment
        from YooKassa before believing it -- trusting the callback body was a
        shipped, exploitable forgery hole. This writes the other columns and
        leaves an existing row's status exactly as it found it.
        """
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO payments (payment_id, status, user_id, purpose, days, created_at, updated_at)
            VALUES ($1, 'pending', $2::uuid, $3, $4, now(), now())
            ON CONFLICT (payment_id) DO UPDATE
            SET user_id = COALESCE(payments.user_id, EXCLUDED.user_id),
                purpose = CASE WHEN payments.purpose = '' THEN EXCLUDED.purpose ELSE payments.purpose END,
                days    = CASE WHEN payments.days = 0 THEN EXCLUDED.days ELSE payments.days END
            """,
            payment_id, user_id, purpose, days,
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

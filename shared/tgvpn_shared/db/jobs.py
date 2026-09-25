"""
Scheduler job outcomes, so a job's silence becomes detectable.

The FREE tier keeps every panel account alive indefinitely and relies on a
background job to move users between paid and free squads. That makes the job
the only thing enforcing expiry -- if it dies quietly, nobody ever loses
access and nothing looks wrong.

Recording each run here is what lets the health monitor tell "ran and found
nothing to do" apart from "did not run". Staleness is judged on
`last_success_at` specifically: a job failing every five minutes has a
perfectly fresh *attempt* and is exactly the case that must still alert.
"""

from __future__ import annotations

from typing import Optional

from .pool import get_pool

_SELECT = """
    SELECT
        job_name,
        EXTRACT(EPOCH FROM last_attempt_at)::bigint AS last_attempt_at,
        EXTRACT(EPOCH FROM last_success_at)::bigint AS last_success_at,
        last_error,
        consecutive_failures,
        last_duration_ms
    FROM job_runs
"""


class JobRunRepository:
    """Last-run bookkeeping for scheduled jobs."""

    async def record_success(self, job_name: str, duration_ms: int | None = None) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO job_runs (
                job_name, last_attempt_at, last_success_at, last_error,
                consecutive_failures, last_duration_ms
            )
            VALUES ($1, now(), now(), NULL, 0, $2)
            ON CONFLICT (job_name) DO UPDATE SET
                last_attempt_at      = now(),
                last_success_at      = now(),
                last_error           = NULL,
                consecutive_failures = 0,
                last_duration_ms     = EXCLUDED.last_duration_ms
            """,
            job_name, duration_ms,
        )

    async def record_failure(self, job_name: str, error: str) -> int:
        """
        Note a failed run and return how many have failed in a row.

        `last_success_at` is left untouched, which is what keeps a repeatedly
        failing job looking stale to the health monitor.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            INSERT INTO job_runs (job_name, last_attempt_at, last_error, consecutive_failures)
            VALUES ($1, now(), $2, 1)
            ON CONFLICT (job_name) DO UPDATE SET
                last_attempt_at      = now(),
                last_error           = EXCLUDED.last_error,
                consecutive_failures = job_runs.consecutive_failures + 1
            RETURNING consecutive_failures
            """,
            job_name, error[:1000],
        )

    async def get(self, job_name: str) -> Optional[dict]:
        pool = await get_pool()
        row = await pool.fetchrow(f"{_SELECT} WHERE job_name = $1", job_name)
        return dict(row) if row else None

    async def get_all(self) -> list[dict]:
        pool = await get_pool()
        return [dict(row) for row in await pool.fetch(f"{_SELECT} ORDER BY job_name")]

    async def find_stale(self, job_name: str, max_age_seconds: int) -> Optional[dict]:
        """
        Return the job's row if it hasn't succeeded recently, else None.

        A job with no row at all counts as stale: it has never succeeded, which
        is the "never actually scheduled" case and just as broken as a crash.
        """
        state = await self.get(job_name)
        if state is None:
            return {
                "job_name": job_name,
                "last_attempt_at": None,
                "last_success_at": None,
                "last_error": None,
                "consecutive_failures": 0,
                "last_duration_ms": None,
            }

        pool = await get_pool()
        is_stale = await pool.fetchval(
            """
            SELECT last_success_at IS NULL
                OR last_success_at < now() - ($2 * INTERVAL '1 second')
            FROM job_runs WHERE job_name = $1
            """,
            job_name, max_age_seconds,
        )
        return state if is_stale else None

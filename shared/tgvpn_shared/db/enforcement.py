"""
What the squad monitors did, kept so the daily report can say it once.

Both monitors used to message the admin chat on any pass that changed
anything. Running every few minutes, that is a notification per routine
demotion, all day -- and the cost is not the noise itself but what it does to
the alerts sitting next to it, which stop being read.

Recording here rather than counting in memory is the whole point: admin_bot
restarts on every deploy, and a daily total that quietly drops the hours
before a restart would be a report that lies without ever looking wrong.
"""

from __future__ import annotations

from .pool import get_pool


class EnforcementRepository:
    """Append-only log of squad/session actions taken by the monitors."""

    async def record(self, job: str, action: str, subject: str | int | None = None) -> None:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO enforcement_events (job, action, subject) VALUES ($1, $2, $3)",
            job, action, "" if subject is None else str(subject)[:200],
        )

    async def summary_since(self, seconds: int) -> dict[str, int]:
        """
        How many of each action in the last `seconds`, as `{action: count}`.

        Actions nothing did are absent rather than zero -- the caller decides
        which ones are worth printing a zero for, and it wants to print zeros
        for the ones it knows about rather than only for the ones that happened.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT action, COUNT(*)::bigint AS count
            FROM enforcement_events
            WHERE ts > now() - ($1 * INTERVAL '1 second')
            GROUP BY action
            """,
            seconds,
        )
        return {str(row["action"]): int(row["count"]) for row in rows}

    async def recent(self, seconds: int, action: str, limit: int = 10) -> list[str]:
        """The subjects of one action, newest first -- for naming names in a report."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT subject
            FROM enforcement_events
            WHERE ts > now() - ($1 * INTERVAL '1 second') AND action = $2
            ORDER BY ts DESC
            LIMIT $3
            """,
            seconds, action, limit,
        )
        return [str(row["subject"]) for row in rows if row["subject"]]

    async def prune(self, older_than_days: int) -> int:
        """Drop rows past their usefulness. Returns how many went."""
        pool = await get_pool()
        result = await pool.execute(
            "DELETE FROM enforcement_events WHERE ts < now() - ($1 * INTERVAL '1 day')",
            older_than_days,
        )
        # asyncpg returns the command tag, e.g. "DELETE 17".
        try:
            return int(str(result).rsplit(" ", 1)[-1])
        except ValueError:
            return 0

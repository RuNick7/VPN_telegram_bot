"""Process-wide asyncpg pool, lazily created on first use.

Each bot process (admin_bot, user_bot polling, user_bot webhook) gets its own
pool. `DATABASE_URL` is a standard Postgres DSN, e.g.
`postgresql://user:pass@host:5432/dbname`.
"""

import os

import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set.")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

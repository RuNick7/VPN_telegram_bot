"""
Bridge for calling the (async-only) Postgres layer from code that is still
synchronous -- specifically user_bot/app/services/remnawave/vpn_service.py,
whose functions are called via `asyncio.to_thread` because they make
synchronous Remnawave HTTP calls (`requests`). Phase 2 unifies the Remnawave
client as natively async and removes the need for this module entirely.

Deliberately does NOT reuse the shared connection pool from db/pool.py: pool
connections are bound to the event loop they were created in, and this
always runs in its own fresh loop via asyncio.run() -- reusing the
long-lived pool here would raise "attached to a different loop". A
standalone connection per call is an acceptable trade for the low call
volume in this still-sync code.
"""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable, TypeVar

import asyncpg

T = TypeVar("T")


def run_sync(fn: Callable[[asyncpg.Connection], Awaitable[T]]) -> T:
    async def _runner() -> T:
        dsn = os.environ["DATABASE_URL"]
        conn = await asyncpg.connect(dsn)
        try:
            return await fn(conn)
        finally:
            await conn.close()

    return asyncio.run(_runner())

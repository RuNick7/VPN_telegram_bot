import os

import pytest

import tgvpn_shared.db.pool as pool_module

# Tests run on the host, outside docker-compose's network, so they hit the
# published host port (5433) rather than the `postgres` hostname the bots use
# inside the compose network.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://tgvpn:tgvpn_local_dev_only@127.0.0.1:5433/tgvpn",
)

_TABLES = "promo_usage, promo_codes, payments, bot_events, admin_operators, users"


@pytest.fixture(autouse=True)
async def _fresh_pool_and_clean_tables():
    """
    Each test gets its own pool bound to its own (function-scoped) event loop,
    and starts against empty tables — this is a local/CI-only Postgres with no
    real data, so truncating between tests is the simplest isolation.
    """
    pool_module._pool = None
    pool = await pool_module.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"TRUNCATE TABLE {_TABLES} RESTART IDENTITY CASCADE")
    yield
    await pool_module.close_pool()

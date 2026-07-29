"""
Bootstrap for the tests that need a real Postgres.

These live in their own directory so the autouse fixture below only applies to
them -- the pure unit tests one level up (settings parsing, Remnawave client
behaviour, squad placement) run anywhere, with no database.
"""

import os
from urllib.parse import urlparse

import pytest

import tgvpn_shared.db.pool as pool_module

# Tests run on the host, outside docker-compose's network, so they hit the
# published host port (5433) rather than the `postgres` hostname the bots use
# inside the compose network.
DEFAULT_TEST_DSN = "postgresql://tgvpn:tgvpn_local_dev_only@127.0.0.1:5433/tgvpn_test"
os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DSN)

# Every table any test writes to. Missing one here is not a harmless
# oversight: state leaks into the next test and makes it pass or fail for
# reasons that have nothing to do with what it is checking.
_TABLES = "promo_usage, promo_codes, payments, bot_events, admin_operators, job_runs, users"

# These tests TRUNCATE every table before each one, so the target database has
# to be disposable. Requiring the name to say so is what stops a stray
# DATABASE_URL -- a copied deploy env, a shell that still has production
# exported -- from wiping real data. This has happened; the guard is not
# hypothetical.
DISPOSABLE_NAME_MARKERS = ("test", "ci", "tmp")


def _database_name(dsn: str) -> str:
    return urlparse(dsn).path.lstrip("/")


def pytest_collection_modifyitems(session, config, items):
    """Refuse to run at all if the target database isn't marked disposable."""
    dsn = os.environ["DATABASE_URL"]
    name = _database_name(dsn)
    if not any(marker in name.lower() for marker in DISPOSABLE_NAME_MARKERS):
        raise pytest.UsageError(
            f"Refusing to run destructive DB tests against database {name!r}.\n"
            f"These tests TRUNCATE every table before each test. Point DATABASE_URL at a\n"
            f"disposable database whose name contains one of {DISPOSABLE_NAME_MARKERS}, e.g.\n"
            f"  createdb tgvpn_test && DATABASE_URL=...://.../tgvpn_test python -m pytest shared/tests/db/"
        )


@pytest.fixture(autouse=True)
async def _fresh_pool_and_clean_tables():
    """
    Each test gets its own pool bound to its own (function-scoped) event loop,
    and starts against empty tables -- the guard above guarantees this is a
    disposable database, so truncating between tests is the simplest isolation.
    """
    pool_module._pool = None
    pool = await pool_module.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"TRUNCATE TABLE {_TABLES} RESTART IDENTITY CASCADE")
    yield
    await pool_module.close_pool()

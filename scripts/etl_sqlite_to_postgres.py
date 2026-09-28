#!/usr/bin/env python3
"""
One-off ETL: migrates the legacy SQLite subscription.db into the new Postgres
schema (migrations/0001_init.up.sql). Run this ONCE during the Phase 1
cutover, after stopping all three writer processes (admin_bot, user_bot
polling, user_bot webhook) so the source file is frozen.

Usage:
    python scripts/etl_sqlite_to_postgres.py \
        --sqlite-path /path/to/subscription.db \
        --database-url postgresql://user:pass@host:5432/dbname

Safe to re-run for users/promo_codes/payments/admin_operators (`ON CONFLICT
DO NOTHING` against real unique constraints) and promo_usage (`WHERE NOT
EXISTS`, since one_time vs multi-use codes have an asymmetric uniqueness
rule the schema doesn't encode as a single index). It does NOT undo or
overwrite rows a second run would conflict with -- if you need to redo a
migration, restore the target schema from migrations/0001_init.down.sql +
up.sql first. bot_events (click telemetry, no natural dedup key) is the one
exception: a re-run duplicates historical events. Harmless for a rare
re-run (nothing else reads that table), but don't run this repeatedly as a
matter of routine.

The legacy `subscription` table has no uniqueness constraint on telegram_id
and may contain duplicate rows per user (a known quirk of the old ad hoc
schema helper). For each telegram_id, this script keeps the row with the
largest subscription_ends (ties broken by largest id) as authoritative --
picking the most generous/most recent subscription state rather than
picking arbitrarily.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
from datetime import datetime, timezone

import asyncpg


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def read_sqlite(sqlite_path: str) -> dict[str, list[dict]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = _row_to_dict
    try:
        data: dict[str, list[dict]] = {}

        if _table_exists(conn, "subscription"):
            rows = conn.execute("SELECT * FROM subscription").fetchall()
            # Dedupe by telegram_id: keep the row with the largest
            # subscription_ends, tie-broken by largest id.
            best_by_telegram_id: dict[int, dict] = {}
            for row in rows:
                tg_id = row.get("telegram_id")
                if tg_id is None:
                    continue
                current = best_by_telegram_id.get(tg_id)
                if current is None:
                    best_by_telegram_id[tg_id] = row
                    continue
                current_key = (current.get("subscription_ends") or 0, current.get("id") or 0)
                row_key = (row.get("subscription_ends") or 0, row.get("id") or 0)
                if row_key > current_key:
                    best_by_telegram_id[tg_id] = row
            data["users"] = list(best_by_telegram_id.values())
            print(
                f"subscription: {len(rows)} source rows -> {len(data['users'])} "
                f"unique telegram_id rows after de-duplication"
            )
        else:
            data["users"] = []

        for table in ("promo_codes", "promo_usage", "payments", "bot_events"):
            data[table] = conn.execute(f"SELECT * FROM {table}").fetchall() if _table_exists(conn, table) else []
            print(f"{table}: {len(data[table])} source rows")

        # admin_bot's legacy operator-role table (same physical file, different
        # table -- see admin_bot/app/db/sqlite.py before it was deleted).
        data["admin_operators"] = (
            conn.execute("SELECT * FROM users").fetchall() if _table_exists(conn, "users") else []
        )
        print(f"admin users (-> admin_operators): {len(data['admin_operators'])} source rows")

        return data
    finally:
        conn.close()


async def write_postgres(pool: asyncpg.Pool, data: dict[str, list[dict]]) -> dict[str, int]:
    written = {}

    async with pool.acquire() as conn:
        count = 0
        for row in data["users"]:
            result = await conn.execute(
                """
                INSERT INTO users (
                    telegram_id, telegram_tag, email, subscription_ends,
                    referrer_tag, is_referred, referred_people, gifted_subscriptions,
                    reminded, nurture_stage, created_at
                ) VALUES ($1, $2, $3, to_timestamp($4), $5, $6, $7, $8, $9, $10, to_timestamp($11))
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                row.get("telegram_id"),
                row.get("telegram_tag") or "",
                (row.get("email") or "").strip() or None,
                int(row.get("subscription_ends") or 0),
                row.get("referrer_tag") or None,
                bool(row.get("is_referred")),
                int(row.get("referred_people") or 0),
                int(row.get("gifted_subscriptions") or 0),
                bool(row.get("reminded")),
                int(row.get("nurture_stage") or 0),
                int(row.get("created_at") or 0),
            )
            if result != "INSERT 0 0":
                count += 1
        written["users"] = count

        count = 0
        for row in data["promo_codes"]:
            result = await conn.execute(
                """
                INSERT INTO promo_codes (code, type, value, is_active, one_time, creator_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (code) DO NOTHING
                """,
                row.get("code"),
                row.get("type"),
                int(row.get("value") or 0),
                bool(row.get("is_active")),
                bool(row.get("one_time")),
                row.get("creator_id"),
            )
            if result != "INSERT 0 0":
                count += 1
        written["promo_codes"] = count

        count = 0
        skipped_orphaned = 0
        for row in data["promo_usage"]:
            try:
                # No unique constraint on (code, telegram_id) to ON CONFLICT
                # against (one_time codes intentionally allow only one row
                # ever, for any user; multi-use codes allow one per user --
                # an asymmetry the schema doesn't encode as a single index).
                # WHERE NOT EXISTS makes this insert idempotent for re-runs.
                result = await conn.execute(
                    """
                    INSERT INTO promo_usage (code, telegram_id, used_at)
                    SELECT $1, $2, now()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM promo_usage WHERE code = $1 AND telegram_id = $2
                    )
                    """,
                    row.get("code"),
                    row.get("telegram_id"),
                )
                if result != "INSERT 0 0":
                    count += 1
            except asyncpg.ForeignKeyViolationError:
                # References a telegram_id whose `users` row didn't survive
                # de-duplication above (or never had a subscription row at
                # all) -- skip rather than abort the whole migration.
                skipped_orphaned += 1
        written["promo_usage"] = count
        if skipped_orphaned:
            print(f"  (skipped {skipped_orphaned} promo_usage rows with no matching users.telegram_id)")

        count = 0
        for row in data["payments"]:
            result = await conn.execute(
                """
                INSERT INTO payments (payment_id, status, created_at, updated_at)
                VALUES ($1, $2, to_timestamp($3), to_timestamp($4))
                ON CONFLICT (payment_id) DO NOTHING
                """,
                row.get("payment_id"),
                row.get("status") or "",
                int(row.get("created_at") or 0),
                int(row.get("updated_at") or 0),
            )
            if result != "INSERT 0 0":
                count += 1
        written["payments"] = count

        count = 0
        for row in data["bot_events"]:
            ts_raw = row.get("ts")
            try:
                ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.now(timezone.utc)
            except ValueError:
                ts = datetime.now(timezone.utc)
            await conn.execute(
                """
                INSERT INTO bot_events (telegram_id, callback_data, step, ts)
                VALUES ($1, $2, $3, $4)
                """,
                row.get("user_id") or 0,
                row.get("callback_data") or "",
                row.get("step") or "",
                ts,
            )
            count += 1
        written["bot_events"] = count

        count = 0
        for row in data["admin_operators"]:
            result = await conn.execute(
                """
                INSERT INTO admin_operators (tg_id, role, selected_server)
                VALUES ($1, $2, $3)
                ON CONFLICT (tg_id) DO NOTHING
                """,
                row.get("tg_id"),
                row.get("role") or "user",
                row.get("selected_server"),
            )
            if result != "INSERT 0 0":
                count += 1
        written["admin_operators"] = count

    return written


async def verify(pool: asyncpg.Pool, source_counts: dict[str, int]) -> None:
    print("\n--- Verification (Postgres row counts) ---")
    async with pool.acquire() as conn:
        for table in ("users", "promo_codes", "promo_usage", "payments", "bot_events", "admin_operators"):
            target_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {target_count} rows in Postgres (source had {source_counts.get(table, '?')})")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path", required=True, help="Path to the legacy subscription.db")
    parser.add_argument("--database-url", required=True, help="Target Postgres DSN")
    args = parser.parse_args()

    print(f"Reading {args.sqlite_path} ...")
    data = read_sqlite(args.sqlite_path)
    source_counts = {name: len(rows) for name, rows in data.items()}

    print(f"\nConnecting to Postgres ...")
    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        print("Writing rows (ON CONFLICT DO NOTHING -- safe to re-run) ...")
        written = await write_postgres(pool, data)
        print("\n--- Rows newly inserted this run ---")
        for table, count in written.items():
            print(f"{table}: {count}")

        await verify(pool, source_counts)
    finally:
        await pool.close()

    print(
        "\nDone. Row counts above should match the source (minus any promo_usage "
        "rows intentionally skipped for orphaned telegram_ids, logged above). "
        "Spot-check a handful of real users before flipping the bots over."
    )


if __name__ == "__main__":
    asyncio.run(main())

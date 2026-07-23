"""SQLite-backed storage for web-only state.

We reuse the same `subscription.db` that user_bot writes to so that the web and
the bot agree on a single source of truth. Web-specific tables are prefixed
with `web_` to keep them out of the bot's logical schema.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from kairaweb.core.settings import ensure_user_bot_on_path


ensure_user_bot_on_path()

from data.db_utils import _ensure_table, get_db  # noqa: E402  (imported after sys.path tweak)


_SCHEMA_READY = False


def _ensure_web_schema(conn: sqlite3.Connection) -> None:
    _ensure_table(
        conn,
        "web_telegram_link_tokens",
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "token_hash": "TEXT NOT NULL UNIQUE",
            "telegram_id": "INTEGER",
            "telegram_username": "TEXT",
            "telegram_first_name": "TEXT",
            "telegram_last_name": "TEXT",
            "status": "TEXT NOT NULL",
            "expires_at": "INTEGER NOT NULL",
            "created_at": "INTEGER NOT NULL",
            "consumed_at": "INTEGER",
        },
        defaults={
            "telegram_id": 0,
            "telegram_username": "",
            "telegram_first_name": "",
            "telegram_last_name": "",
            "status": "pending",
            "expires_at": 0,
            "created_at": 0,
            "consumed_at": 0,
        },
        indexes=[
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_web_tg_link_token_hash ON web_telegram_link_tokens(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_web_tg_link_status ON web_telegram_link_tokens(status)",
        ],
    )
    _ensure_table(
        conn,
        "web_magic_links",
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "token_hash": "TEXT NOT NULL UNIQUE",
            "purpose": "TEXT NOT NULL",
            "telegram_id": "INTEGER NOT NULL",
            "email": "TEXT NOT NULL",
            "expires_at": "INTEGER NOT NULL",
            "used_at": "INTEGER",
            "created_at": "INTEGER NOT NULL",
        },
        defaults={
            "purpose": "login_magic",
            "telegram_id": 0,
            "email": "",
            "expires_at": 0,
            "used_at": 0,
            "created_at": 0,
        },
        indexes=[
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_web_magic_token_hash ON web_magic_links(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_web_magic_email ON web_magic_links(email)",
        ],
    )
    _ensure_table(
        conn,
        "web_rate_limit_hits",
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "bucket": "TEXT NOT NULL",
            "ip": "TEXT NOT NULL",
            "hit_at": "INTEGER NOT NULL",
        },
        defaults={"bucket": "auth", "ip": "", "hit_at": 0},
        indexes=[
            "CREATE INDEX IF NOT EXISTS idx_web_rate_limit_bucket_ip ON web_rate_limit_hits(bucket, ip, hit_at)",
        ],
    )
    _ensure_table(
        conn,
        "web_push_subscriptions",
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "telegram_id": "INTEGER NOT NULL",
            "endpoint": "TEXT NOT NULL UNIQUE",
            "p256dh": "TEXT NOT NULL",
            "auth": "TEXT NOT NULL",
            "user_agent": "TEXT",
            "created_at": "INTEGER NOT NULL",
            "last_used_at": "INTEGER",
        },
        defaults={
            "telegram_id": 0,
            "endpoint": "",
            "p256dh": "",
            "auth": "",
            "user_agent": "",
            "created_at": 0,
            "last_used_at": 0,
        },
        indexes=[
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_web_push_endpoint ON web_push_subscriptions(endpoint)",
            "CREATE INDEX IF NOT EXISTS idx_web_push_user ON web_push_subscriptions(telegram_id)",
        ],
    )


@contextmanager
def web_db() -> Iterator[sqlite3.Connection]:
    global _SCHEMA_READY
    with get_db() as conn:
        if not _SCHEMA_READY:
            _ensure_web_schema(conn)
            conn.commit()
            _SCHEMA_READY = True
        yield conn


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_raw_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


# ---- Telegram link tokens ----

def create_pending_telegram_link(*, ttl_seconds: int) -> tuple[str, int]:
    raw_token = generate_raw_token()
    now_ts = int(time.time())
    expires_at = now_ts + ttl_seconds
    with web_db() as conn:
        conn.execute(
            """
            INSERT INTO web_telegram_link_tokens
                (token_hash, status, expires_at, created_at)
            VALUES (?, 'pending', ?, ?)
            """,
            (token_hash(raw_token), expires_at, now_ts),
        )
        conn.commit()
    return raw_token, expires_at


def get_telegram_link_by_token(raw_token: str) -> dict[str, Any] | None:
    with web_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM web_telegram_link_tokens
            WHERE token_hash = ?
            """,
            (token_hash(raw_token),),
        ).fetchone()
        return dict(row) if row else None


def confirm_telegram_link_by_token(
    raw_token: str,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict[str, Any] | None:
    """Mark a pending token as confirmed. Returns updated row or None."""
    now_ts = int(time.time())
    with web_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            UPDATE web_telegram_link_tokens
            SET telegram_id = ?,
                telegram_username = ?,
                telegram_first_name = ?,
                telegram_last_name = ?,
                status = 'confirmed',
                consumed_at = ?
            WHERE token_hash = ?
              AND status = 'pending'
              AND expires_at > ?
            """,
            (
                int(telegram_id),
                username or "",
                first_name or "",
                last_name or "",
                now_ts,
                token_hash(raw_token),
                now_ts,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM web_telegram_link_tokens WHERE token_hash = ?",
            (token_hash(raw_token),),
        ).fetchone()
        return dict(row) if row else None


def cleanup_expired_telegram_links() -> None:
    now_ts = int(time.time())
    with web_db() as conn:
        conn.execute(
            "DELETE FROM web_telegram_link_tokens WHERE expires_at <= ? AND status = 'pending'",
            (now_ts,),
        )
        conn.commit()


# ---- Magic links ----

def create_magic_link(
    *,
    purpose: str,
    telegram_id: int,
    email: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    raw_token = generate_raw_token()
    now_ts = int(time.time())
    expires_at = now_ts + ttl_seconds
    with web_db() as conn:
        conn.execute(
            """
            INSERT INTO web_magic_links
                (token_hash, purpose, telegram_id, email, expires_at, used_at, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (token_hash(raw_token), purpose, int(telegram_id), email, expires_at, now_ts),
        )
        conn.commit()
    return raw_token, expires_at


def consume_magic_link(raw_token: str) -> dict[str, Any] | None:
    """Atomically mark a magic-link as used. Returns row only on first use."""
    now_ts = int(time.time())
    with web_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            UPDATE web_magic_links
            SET used_at = ?
            WHERE token_hash = ?
              AND used_at IS NULL
              AND expires_at > ?
            """,
            (now_ts, token_hash(raw_token), now_ts),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM web_magic_links WHERE token_hash = ?",
            (token_hash(raw_token),),
        ).fetchone()
        return dict(row) if row else None


def cleanup_expired_magic_links() -> None:
    now_ts = int(time.time())
    with web_db() as conn:
        conn.execute(
            "DELETE FROM web_magic_links WHERE expires_at <= ? AND used_at IS NULL",
            (now_ts,),
        )
        conn.commit()


# ---- Push subscriptions ----

def upsert_push_subscription(
    *,
    telegram_id: int,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None = None,
) -> None:
    now_ts = int(time.time())
    with web_db() as conn:
        conn.execute(
            """
            INSERT INTO web_push_subscriptions
                (telegram_id, endpoint, p256dh, auth, user_agent, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                telegram_id = excluded.telegram_id,
                p256dh      = excluded.p256dh,
                auth        = excluded.auth,
                user_agent  = excluded.user_agent,
                last_used_at = excluded.last_used_at
            """,
            (int(telegram_id), endpoint, p256dh, auth, user_agent or "", now_ts, now_ts),
        )
        conn.commit()


def delete_push_subscription_by_endpoint(endpoint: str) -> int:
    with web_db() as conn:
        cursor = conn.execute(
            "DELETE FROM web_push_subscriptions WHERE endpoint = ?",
            (endpoint,),
        )
        conn.commit()
        return cursor.rowcount


def list_push_subscriptions(telegram_id: int) -> list[dict[str, Any]]:
    with web_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM web_push_subscriptions WHERE telegram_id = ?",
            (int(telegram_id),),
        ).fetchall()
        return [dict(row) for row in rows]


def touch_push_subscription(endpoint: str) -> None:
    with web_db() as conn:
        conn.execute(
            "UPDATE web_push_subscriptions SET last_used_at = ? WHERE endpoint = ?",
            (int(time.time()), endpoint),
        )
        conn.commit()


# ---- Rate limit ----

def record_rate_limit_hit(*, bucket: str, ip: str, window_seconds: int, max_hits: int) -> bool:
    """Returns True if the request is allowed, False if it should be rejected."""
    now_ts = int(time.time())
    cutoff = now_ts - max(1, window_seconds)
    with web_db() as conn:
        conn.execute(
            "DELETE FROM web_rate_limit_hits WHERE bucket = ? AND hit_at < ?",
            (bucket, cutoff),
        )
        cursor = conn.execute(
            "SELECT COUNT(1) FROM web_rate_limit_hits WHERE bucket = ? AND ip = ? AND hit_at >= ?",
            (bucket, ip, cutoff),
        )
        count = int(cursor.fetchone()[0] or 0)
        if count >= max_hits:
            conn.commit()
            return False
        conn.execute(
            "INSERT INTO web_rate_limit_hits (bucket, ip, hit_at) VALUES (?, ?, ?)",
            (bucket, ip, now_ts),
        )
        conn.commit()
        return True

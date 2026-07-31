"""
One-time tokens that attach a Telegram account to a website account.

The website mints a token and hands the user a `t.me/<bot>?start=link_<token>`
link; the bot redeems it on the other side. That is the whole handshake, and
it works because the two ends are the same person by construction: only
someone holding the browser session could have been given the link, and only
someone in the chat can redeem it.

Tokens are stored hashed, like sessions and magic links, so a database dump
yields nothing that can be redeemed.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .pool import get_pool


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class AccountLinkRepository:
    async def create(self, token: str, user_id: str, ttl_seconds: int) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO account_link_tokens (token_hash, user_id, expires_at)
            VALUES ($1, $2::uuid, now() + make_interval(secs => $3))
            """,
            hash_token(token), user_id, ttl_seconds,
        )

    async def consume(self, token: str) -> Optional[str]:
        """
        Redeem a link token, returning the website account's id.

        The `consumed_at IS NULL` guard is in the UPDATE so redemption is
        atomic: a link forwarded to somebody else, or opened twice because
        Telegram prefetched it, can only ever attach one account. A second
        attempt matches no row and is indistinguishable from an invalid token,
        which is what the caller should say anyway.
        """
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            UPDATE account_link_tokens SET consumed_at = now()
            WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
            RETURNING user_id
            """,
            hash_token(token),
        )
        return str(row["user_id"]) if row else None

    async def delete_expired(self) -> int:
        pool = await get_pool()
        result = await pool.execute(
            "DELETE FROM account_link_tokens WHERE expires_at < now() - interval '1 day'"
        )
        return int(result.split()[-1]) if result else 0

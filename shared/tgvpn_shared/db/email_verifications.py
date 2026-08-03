"""
One-time tokens that attach an email address to an account that already exists.

Not the same thing as a magic link, and the difference matters. A magic link is
keyed by *address* and signs somebody in; it deliberately reveals nothing about
whether that address has an account, which is why the account is only resolved
at redemption. These are keyed by *user*: the account is already known, and
what the token proves is that whoever is driving it also controls the mailbox.

Stored hashed, like sessions, magic links and account-link tokens, so a
database dump yields nothing that can be redeemed.

Only minting lives here. **Redemption is the website's**, in Go, and there is
one implementation of it on purpose: confirming a token also pays the link
bonus and writes the address, and a second copy of those rules is a second
place for them to disagree about how many free days somebody is owed. The bot
posts the letter; the link in it lands on the site either way.
"""

from __future__ import annotations

import hashlib

from .pool import get_pool


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class EmailVerificationRepository:
    async def create(self, token: str, user_id: str, email: str, ttl_seconds: int) -> None:
        """
        Issue a token, replacing any this user already had outstanding.

        Replacing rather than accumulating: someone who mistypes their address
        and asks again should not leave a live token pointing at the typo, and
        the newest request is the only one they are looking at.
        """
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM email_verifications WHERE user_id = $1::uuid AND consumed_at IS NULL",
                    user_id,
                )
                await connection.execute(
                    """
                    INSERT INTO email_verifications (token_hash, user_id, email, expires_at)
                    VALUES ($1, $2::uuid, $3, now() + make_interval(secs => $4))
                    """,
                    hash_token(token), user_id, email.strip().lower(), ttl_seconds,
                )

    async def delete_expired(self) -> int:
        pool = await get_pool()
        result = await pool.execute(
            "DELETE FROM email_verifications WHERE expires_at < now() - interval '1 day'"
        )
        return int(result.split()[-1]) if result else 0

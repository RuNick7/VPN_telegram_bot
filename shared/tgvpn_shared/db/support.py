"""
Support tickets, from admin_bot's side of the table.

The website writes tickets and the customer's messages; this side carries them
into the operators' Telegram chats, records an operator's answer, and tells
the customer one has arrived. Nothing here creates a ticket -- that belongs to
the site, where the customer is signed in -- and nothing on the site can write
an answer. Each side owns the rows it is the only one able to vouch for.

`support_messages.delivered_at` is the outbox for both directions. On a
customer's message it means "the operators have it"; on an operator's, "the
customer has been told". Reading it back is how a message written while
Telegram was unreachable still arrives, just later.
"""

from __future__ import annotations

from typing import Sequence

from .pool import get_pool

# (file name, content type, bytes) -- one file of an operator's answer.
AttachmentUpload = tuple[str, str, bytes]

_ATTACHMENTS = """
    SELECT
        a.id::text AS id,
        a.message_id,
        a.file_name,
        a.content_type,
        a.size_bytes,
        NOT EXISTS (
            SELECT 1 FROM support_attachment_data d WHERE d.attachment_id = a.id
        ) AS purged
    FROM support_attachments a
    WHERE a.message_id = ANY($1::bigint[])
    ORDER BY a.created_at, a.id
"""


class SupportRepository:
    """Tickets, their messages, and which Telegram message carries which."""

    async def _attachments_of(self, message_ids: Sequence[int]) -> dict[int, list[dict]]:
        """Attachment metadata -- never the bytes -- grouped by message."""
        if not message_ids:
            return {}
        pool = await get_pool()
        grouped: dict[int, list[dict]] = {}
        for row in await pool.fetch(_ATTACHMENTS, list(message_ids)):
            grouped.setdefault(int(row["message_id"]), []).append(dict(row))
        return grouped

    async def attachment_data(self, attachment_id: str) -> bytes | None:
        """One file's bytes, or None once it has been purged."""
        pool = await get_pool()
        data = await pool.fetchval(
            "SELECT data FROM support_attachment_data WHERE attachment_id = $1::uuid",
            attachment_id,
        )
        return bytes(data) if data is not None else None

    # -- customer -> operators ---------------------------------------------

    async def pending_customer_messages(self, limit: int = 20) -> list[dict]:
        """
        Customer messages the operators have not been shown, oldest first.

        Oldest first is load-bearing: a ticket's opening message is what the
        rest reply to in Telegram, so it has to land before anything after it.
        Each row carries what a ticket card needs to say who is asking,
        because an operator answering in a chat has nothing else to go on.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                m.id,
                m.ticket_id,
                m.body,
                EXTRACT(EPOCH FROM m.created_at)::bigint AS created_at,
                m.delivery_attempts,
                t.subject,
                t.status,
                NOT EXISTS (
                    SELECT 1 FROM support_messages e
                    WHERE e.ticket_id = m.ticket_id AND e.id < m.id
                ) AS opens_ticket,
                u.id::text AS user_id,
                u.email,
                u.telegram_id,
                u.telegram_tag,
                EXTRACT(EPOCH FROM u.subscription_ends)::bigint AS subscription_ends
            FROM support_messages m
            JOIN support_tickets t ON t.id = m.ticket_id
            JOIN users u ON u.id = t.user_id
            WHERE m.delivered_at IS NULL AND m.author = 'user'
            ORDER BY m.id
            LIMIT $1
            """,
            limit,
        )
        attachments = await self._attachments_of([row["id"] for row in rows])
        return [
            {**dict(row), "attachments": attachments.get(int(row["id"]), [])}
            for row in rows
        ]

    async def delivered_parts(self, support_message_id: int) -> dict[tuple[int, str | None], int]:
        """
        What of one message already sits in which chat.

        Keyed `(chat_id, attachment_id)`, with `None` standing for the text,
        and valued with the Telegram message id -- the first one, when a long
        text went out in pieces, since that is what its files reply to.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT chat_id, attachment_id::text AS attachment_id, telegram_message_id
            FROM support_telegram_messages
            WHERE support_message_id = $1
            ORDER BY telegram_message_id
            """,
            support_message_id,
        )
        parts: dict[tuple[int, str | None], int] = {}
        for row in rows:
            key = (int(row["chat_id"]), row["attachment_id"])
            parts.setdefault(key, int(row["telegram_message_id"]))
        return parts

    async def record_telegram_message(
        self,
        chat_id: int,
        telegram_message_id: int,
        ticket_id: int,
        kind: str,
        *,
        support_message_id: int | None = None,
        attachment_id: str | None = None,
    ) -> None:
        """Remember that a Telegram message belongs to a ticket."""
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO support_telegram_messages (
                chat_id, telegram_message_id, ticket_id, kind,
                support_message_id, attachment_id
            )
            VALUES ($1, $2, $3, $4, $5, $6::uuid)
            ON CONFLICT (chat_id, telegram_message_id) DO NOTHING
            """,
            chat_id, telegram_message_id, ticket_id, kind,
            support_message_id, attachment_id,
        )

    async def card_for(self, ticket_id: int, chat_id: int) -> int | None:
        """
        The Telegram message a ticket's later messages reply to in this chat.

        The newest card, not the first: an operator who reopens a ticket from
        the list gets a fresh card at the bottom of the chat, and a follow-up
        threaded onto one from last week would be answered from the wrong end
        of a long scroll.
        """
        pool = await get_pool()
        return await pool.fetchval(
            """
            SELECT telegram_message_id
            FROM support_telegram_messages
            WHERE ticket_id = $1 AND chat_id = $2 AND kind = 'card'
            ORDER BY created_at DESC, telegram_message_id DESC
            LIMIT 1
            """,
            ticket_id, chat_id,
        )

    async def ticket_for_telegram_message(self, chat_id: int, telegram_message_id: int) -> int | None:
        """Which ticket an operator is replying to, if any."""
        pool = await get_pool()
        return await pool.fetchval(
            """
            SELECT ticket_id FROM support_telegram_messages
            WHERE chat_id = $1 AND telegram_message_id = $2
            """,
            chat_id, telegram_message_id,
        )

    async def mark_delivered(self, *message_ids: int) -> None:
        if not message_ids:
            return
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE support_messages
            SET delivered_at = now(), last_delivery_error = NULL
            WHERE id = ANY($1::bigint[]) AND delivered_at IS NULL
            """,
            list(message_ids),
        )

    async def record_delivery_failure(self, message_id: int, error: str) -> int:
        """Count a failed attempt and return how many there have been."""
        pool = await get_pool()
        attempts = await pool.fetchval(
            """
            UPDATE support_messages
            SET delivery_attempts = delivery_attempts + 1, last_delivery_error = $2
            WHERE id = $1
            RETURNING delivery_attempts
            """,
            message_id, error[:1000],
        )
        return int(attempts or 0)

    # -- the operators' side -------------------------------------------------

    async def add_admin_reply(
        self,
        ticket_id: int,
        admin_telegram_id: int,
        body: str,
        files: Sequence[AttachmentUpload] = (),
    ) -> int | None:
        """
        Record an operator's answer. Returns its message id, or None if the
        ticket does not exist.

        Answering a closed ticket reopens it as answered: an operator who
        writes after the customer closed it has something to add, and the
        customer has to be able to see it and reply. `close_announced_at` is
        reset with it, so a later close by the customer is announced again.
        """
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                found = await connection.fetchval(
                    """
                    UPDATE support_tickets SET
                        status             = 'answered',
                        updated_at         = now(),
                        closed_at          = NULL,
                        closed_by          = NULL,
                        close_announced_at = NULL
                    WHERE id = $1
                    RETURNING id
                    """,
                    ticket_id,
                )
                if found is None:
                    return None
                message_id = await connection.fetchval(
                    """
                    INSERT INTO support_messages (ticket_id, author, admin_telegram_id, body)
                    VALUES ($1, 'admin', $2, $3)
                    RETURNING id
                    """,
                    ticket_id, admin_telegram_id, body,
                )
                for file_name, content_type, data in files:
                    attachment_id = await connection.fetchval(
                        """
                        INSERT INTO support_attachments
                            (message_id, file_name, content_type, size_bytes)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                        """,
                        message_id, file_name, content_type, len(data),
                    )
                    await connection.execute(
                        "INSERT INTO support_attachment_data (attachment_id, data) VALUES ($1, $2)",
                        attachment_id, data,
                    )
        return int(message_id)

    async def get_ticket(self, ticket_id: int) -> dict | None:
        """A ticket with the customer it belongs to."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                t.id,
                t.subject,
                t.status,
                t.closed_by,
                EXTRACT(EPOCH FROM t.created_at)::bigint AS created_at,
                EXTRACT(EPOCH FROM t.updated_at)::bigint AS updated_at,
                u.id::text AS user_id,
                u.email,
                u.telegram_id,
                u.telegram_tag,
                EXTRACT(EPOCH FROM u.subscription_ends)::bigint AS subscription_ends,
                (SELECT COUNT(*) FROM support_messages m WHERE m.ticket_id = t.id) AS message_count
            FROM support_tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = $1
            """,
            ticket_id,
        )
        return dict(row) if row else None

    async def thread(self, ticket_id: int) -> list[dict]:
        """Every message of a ticket in order, each with its files' metadata."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                id,
                author,
                admin_telegram_id,
                body,
                EXTRACT(EPOCH FROM created_at)::bigint AS created_at
            FROM support_messages
            WHERE ticket_id = $1
            ORDER BY id
            """,
            ticket_id,
        )
        attachments = await self._attachments_of([row["id"] for row in rows])
        return [
            {**dict(row), "attachments": attachments.get(int(row["id"]), [])}
            for row in rows
        ]

    async def latest_customer_message(self, ticket_id: int) -> dict | None:
        """What the customer said last -- what a fresh card should show."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT id, body, EXTRACT(EPOCH FROM created_at)::bigint AS created_at
            FROM support_messages
            WHERE ticket_id = $1 AND author = 'user'
            ORDER BY id DESC
            LIMIT 1
            """,
            ticket_id,
        )
        if row is None:
            return None
        attachments = await self._attachments_of([row["id"]])
        return {**dict(row), "attachments": attachments.get(int(row["id"]), [])}

    async def close(self, ticket_id: int) -> bool:
        """Close on the operators' word. False when it was closed already."""
        pool = await get_pool()
        result = await pool.execute(
            """
            UPDATE support_tickets SET
                status     = 'closed',
                closed_at  = now(),
                closed_by  = 'admin',
                updated_at = now()
            WHERE id = $1 AND status <> 'closed'
            """,
            ticket_id,
        )
        return result != "UPDATE 0"

    async def reopen(self, ticket_id: int) -> bool:
        """Put a closed ticket back in the queue. False when it was not closed."""
        pool = await get_pool()
        result = await pool.execute(
            """
            UPDATE support_tickets SET
                status             = 'open',
                closed_at          = NULL,
                closed_by          = NULL,
                close_announced_at = NULL,
                updated_at         = now()
            WHERE id = $1 AND status = 'closed'
            """,
            ticket_id,
        )
        return result != "UPDATE 0"

    async def count_waiting(self) -> int:
        """Tickets waiting on an operator."""
        pool = await get_pool()
        return int(
            await pool.fetchval("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'") or 0
        )

    async def waiting_page(self, limit: int, offset: int) -> list[dict]:
        """
        The queue, longest-waiting first.

        Oldest first rather than newest: the list exists to answer "who has
        been kept waiting", and a fresh ticket on top would push the one from
        yesterday off the first page.
        """
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                t.id,
                t.subject,
                EXTRACT(EPOCH FROM t.updated_at)::bigint AS updated_at,
                u.email,
                u.telegram_tag,
                u.telegram_id
            FROM support_tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.status = 'open'
            ORDER BY t.updated_at, t.id
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        return [dict(row) for row in rows]

    # -- operators -> customer -----------------------------------------------

    async def pending_operator_replies(self, limit: int = 50) -> list[dict]:
        """Operators' answers the customer has not been told about, oldest first."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT
                m.id,
                m.ticket_id,
                m.body,
                t.subject,
                u.telegram_id,
                (SELECT COUNT(*) FROM support_attachments a WHERE a.message_id = m.id)
                    AS attachment_count
            FROM support_messages m
            JOIN support_tickets t ON t.id = m.ticket_id
            JOIN users u ON u.id = t.user_id
            WHERE m.delivered_at IS NULL AND m.author = 'admin'
            ORDER BY m.id
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def pending_close_announcements(self, limit: int = 20) -> list[dict]:
        """Tickets the customer closed that the operators have not heard about."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT id, subject
            FROM support_tickets
            WHERE status = 'closed' AND closed_by = 'user' AND close_announced_at IS NULL
            ORDER BY closed_at, id
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def mark_close_announced(self, ticket_id: int) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE support_tickets SET close_announced_at = now() WHERE id = $1",
            ticket_id,
        )

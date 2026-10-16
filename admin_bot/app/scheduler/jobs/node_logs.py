"""
Sends the operators each node's log lines for a customer's server-check report.

When a report has reached the admin chats (support_outbox delivers it as the
customer's message), this asks every vpncheck-agent in NODE_LOG_AGENTS for
its side of the run and replies to the ticket's card with one text file. See
app/services/node_logs.py for what the agents are asked and how.

A loop of its own, not part of the outbox pass: the agents may take a minute
to answer, and tickets should not wait behind them.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from tgvpn_shared.db import SupportDiagnosticsRepository, SupportRepository

from app.config.settings import settings
from app.services.node_logs import (
    Agent,
    ask_agents,
    build_query,
    panel_names,
    parse_report,
    render,
)
from app.services.support import chat_unreachable, send_file

logger = logging.getLogger(__name__)

POLL_SECONDS = 15

_support = SupportRepository()
_diagnostics = SupportDiagnosticsRepository()


async def run_node_logs(bot: Bot, agents: list[Agent]) -> None:
    """Forever: one pass, a pause, again. Never raises, except to be cancelled."""
    while True:
        try:
            await run_pass(bot, agents)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Node logs pass failed: %s", exc, exc_info=True)
        await asyncio.sleep(POLL_SECONDS)


async def run_pass(bot: Bot, agents: list[Agent]) -> None:
    chats = settings.admin_ids
    if not chats:
        return
    for request in await _diagnostics.pending_node_logs():
        await send_node_logs(bot, request, agents, chats)


async def send_node_logs(bot: Bot, request: dict, agents: list[Agent], chats: list[int]) -> None:
    ticket_id = int(request["ticket_id"])
    data = await _support.attachment_data(request["attachment_id"]) if request["attachment_id"] else None
    windows, clock_checked = parse_report(data.decode("utf-8", "replace")) if data else ([], True)
    if not windows:
        # A report with no server in it, or its file already purged: there
        # is nothing to look for.
        await _diagnostics.mark_node_logs(int(request["id"]))
        return

    query = build_query(windows, clock_checked, panel_names(request))
    answers = await ask_agents(agents, query)
    document, caption = render(ticket_id, request["subject"], query, answers)
    for chat_id in chats:
        card = await _support.card_for(ticket_id, chat_id)
        try:
            sent = await send_file(
                bot, chat_id, name=f"node-logs-{ticket_id}.txt", content_type="text/plain",
                data=document, caption=caption, reply_to_id=card,
            )
        except Exception as exc:
            if chat_unreachable(exc):
                continue
            raise
        await _support.record_telegram_message(chat_id, sent.message_id, ticket_id, "notice")
    await _diagnostics.mark_node_logs(int(request["id"]))

"""
The nodes' side of a customer's server-check report.

Each node runs vpncheck-agent (vpncheck/cmd/vpncheck-agent), which searches
the node's Xray logs for one run. The report says, for every server, when its
node saw the run and the marker host the run asked for through it; the agent
finds the marker in its access log and with it the customer's panel user and
address (vpncheck/internal/nodelog). This module reads the windows out of the
report, asks every agent at once, and renders what came back as one text
file for the operators.

The agents' answers hold the customer's address, so they go to the admin
chats only -- never into the ticket, which the customer reads.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from html import escape
from urllib.parse import urlsplit

import aiohttp

logger = logging.getLogger(__name__)

# What the agent accepts; a report past it is cut, not refused.
MAX_WINDOWS = 100
# Around each window. Corrected against Cloudflare's clock, a customer's
# computer is off by a fraction of a second; uncorrected, by anything.
SLACK_CHECKED_CLOCK = 5
SLACK_UNCHECKED_CLOCK = 120
AGENT_TIMEOUT_SECONDS = 90
# Far under Telegram's 50 MB for a document, and more than an operator reads.
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class Agent:
    name: str
    url: str
    token: str
    fingerprint: bytes


def parse_agents(raw: str) -> list[Agent]:
    """
    NODE_LOG_AGENTS: name=https://token@host:port#sha256, as each agent prints
    it, separated by spaces or commas. An entry that does not parse is logged
    -- by name and position, never with its token -- and left out.
    """
    agents = []
    for position, entry in enumerate(e for e in re.split(r"[\s,;]+", raw.strip()) if e):
        name, _, url = entry.partition("=")
        try:
            parts = urlsplit(url)
            fingerprint = bytes.fromhex(parts.fragment)
            valid = (
                name and parts.scheme == "https" and parts.username and parts.hostname
                and parts.port and len(fingerprint) == 32
            )
        except ValueError:
            valid = False
        if not valid:
            logger.error("NODE_LOG_AGENTS: entry %d (%s) is not name=https://token@host:port#sha256",
                         position + 1, name or "?")
            continue
        host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        agents.append(Agent(name, f"https://{host}:{parts.port}", parts.username, fingerprint))
    return agents


# -- the report -------------------------------------------------------------------

# Written by vpncheck/internal/report; TestNodeWindowAndMarker there pins the
# same lines this reads.
_SEPARATOR = "\n" + "=" * 78 + "\n"
_SERVER = re.compile(r"^Сервер: (?P<server>\S+) — .+ — (?P<verdict>[^\n]+)$", re.M)
_WINDOW = re.compile(r"^Время на ноде \(UTC\): (?P<from>\S+) — (?P<to>\S+)$", re.M)
_MARKER = re.compile(r"^Метка в логе ноды: (?P<marker>\S+)", re.M)
_UNCHECKED_CLOCK = "Часы компьютера: не сверены"


def parse_report(text: str) -> tuple[list[dict], bool]:
    """The report's windows, one per server checked, and whether its clock was checked."""
    windows = []
    for section in text.split(_SEPARATOR)[1:]:
        server, window = _SERVER.search(section), _WINDOW.search(section)
        if not (server and window):
            continue
        marker = _MARKER.search(section)
        windows.append({
            "server": server["server"],
            "from": window["from"],
            "to": window["to"],
            "marker": marker["marker"] if marker else "",
            "failed": server["verdict"].strip() != "РАБОТАЕТ",
        })
    return windows[:MAX_WINDOWS], _UNCHECKED_CLOCK not in text


def panel_names(request: dict) -> list[str]:
    """What the customer may be called in the nodes' logs, for when no marker turns up."""
    names = [request.get("remnawave_username"), request.get("remnawave_uuid")]
    if request.get("telegram_id"):
        # Accounts older than the identity rework are named by Telegram id.
        names.append(str(request["telegram_id"]))
    return [name for name in names if name]


def build_query(windows: list[dict], clock_checked: bool, users: list[str]) -> dict:
    return {
        "windows": windows,
        "users": users,
        "slack_seconds": SLACK_CHECKED_CLOCK if clock_checked else SLACK_UNCHECKED_CLOCK,
    }


# -- the agents -------------------------------------------------------------------


@dataclass
class Answer:
    agent: Agent
    result: dict | None = None
    error: str = ""


async def _search(session: aiohttp.ClientSession, agent: Agent, query: dict) -> dict:
    async with session.post(
        f"{agent.url}/v1/search",
        json=query,
        headers={"Authorization": f"Bearer {agent.token}"},
        # The agent's certificate is its own; this pins it instead of
        # trusting a CA, and refuses anything else answering on that port.
        ssl=aiohttp.Fingerprint(agent.fingerprint),
    ) as response:
        if response.status != 200:
            detail = (await response.text())[:200].strip()
            raise RuntimeError(f"HTTP {response.status}: {detail}")
        return await response.json()


def _describe(error: BaseException) -> str:
    if isinstance(error, aiohttp.ServerFingerprintMismatch):
        return "отвечает не тот сертификат: агент переустановлен или это не он — обновите строку в NODE_LOG_AGENTS"
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return f"не ответил за {AGENT_TIMEOUT_SECONDS} с"
    if isinstance(error, aiohttp.ClientConnectorError):
        return f"нет соединения: {error.os_error or error}"
    return str(error) or type(error).__name__


async def ask_agents(agents: list[Agent], query: dict, timeout: float = AGENT_TIMEOUT_SECONDS) -> list[Answer]:
    """Every agent at once; one that fails is an answer saying so, never an exception."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        results = await asyncio.gather(
            *(_search(session, agent, query) for agent in agents), return_exceptions=True
        )
    answers = []
    for agent, result in zip(agents, results):
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, BaseException):
            logger.warning("Node log agent %s failed: %s", agent.name, result)
            answers.append(Answer(agent, error=_describe(result)))
        else:
            answers.append(Answer(agent, result=result))
    return answers


# -- what the operators get ---------------------------------------------------------


def render(ticket_id: int, subject: str, query: dict, answers: list[Answer]) -> tuple[bytes, str]:
    """The document and its caption (HTML)."""
    lines = [
        f"Логи нод по проверке серверов, обращение #{ticket_id} · {subject}",
        f"Искал по метке и пользователю в окне ±{query['slack_seconds']} с вокруг проверки каждого сервера"
        + ("" if query["slack_seconds"] == SLACK_CHECKED_CLOCK else " (часы клиента не сверены)"),
        "",
    ]
    for answer in answers:
        if answer.error:
            lines.append(f"Нода {answer.agent.name}: не ответила — {answer.error}")
            continue
        unreadable = [f for f in answer.result.get("files") or [] if f.get("error")]
        status = "ответила" if not unreadable else "ответила, но не читает: " + "; ".join(
            f"{f['path']} ({f['error']})" for f in unreadable
        )
        lines.append(f"Нода {answer.agent.name}: {status}")

    found_on: set[str] = set()
    for index, window in enumerate(query["windows"]):
        lines += ["", "=" * 78, (
            f"{window['server']} · {window['from']} — {window['to']} · "
            f"{'с ошибками' if window['failed'] else 'работал'} · метка {window['marker'] or '—'}"
        )]
        anything = False
        for answer in answers:
            if not answer.result:
                continue
            sections = answer.result.get("sections") or []
            section = sections[index] if index < len(sections) else None
            if not section or not section.get("lines"):
                continue
            anything = True
            if section.get("attributed"):
                found_on.add(answer.agent.name)
                who = ", ".join(section.get("emails") or []) or "—"
                where = ", ".join(section.get("addresses") or []) or "—"
                lines.append(f"-- нода {answer.agent.name}: пользователь {who}, адрес {where}")
            else:
                lines.append(
                    f"-- нода {answer.agent.name}: метки нет, строки ошибок ноды за это время "
                    f"(могут быть и о других клиентах)"
                )
            lines += section["lines"]
            if section.get("truncated"):
                lines.append("... дальше строки обрезаны")
        if not anything:
            lines.append(
                "-- ни на одной ноде нет строк этой проверки: метка не дошла до ноды, то есть сервер не принял клиента"
                if window["failed"] else
                "-- ни на одной ноде нет строк этой проверки: проверьте, что access-лог Xray включён"
            )

    data = "\n".join(lines).encode("utf-8") + b"\n"
    if len(data) > MAX_DOCUMENT_BYTES:
        data = data[:MAX_DOCUMENT_BYTES].decode("utf-8", "ignore").encode("utf-8") + "\n... файл обрезан\n".encode()

    failed = [escape(answer.agent.name) for answer in answers if answer.error]
    caption = f"🖥 Логи нод по проверке в <b>#{ticket_id}</b>: " + (
        "строки клиента нашлись на " + ", ".join(escape(name) for name in sorted(found_on))
        if found_on else "строк клиента не нашлось"
    )
    if failed:
        caption += "; не ответили: " + ", ".join(failed)
    return data, caption

"""
The nodes' side of a customer's server-check report.

Pinned here: that the bot reads the windows out of the report vpncheck
writes (the same lines vpncheck's own TestNodeWindowAndMarker pins), that
it reaches an agent only through the certificate it was given, and that what
comes back reaches the admin chats -- and only them.
"""

import datetime
import logging
import ssl
from types import SimpleNamespace

import pytest
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.scheduler.jobs import node_logs as job
from app.services import node_logs
from app.services.node_logs import Agent, Answer

ADMIN, OTHER = 111, 222
TOKEN = "A" * 43
FINGERPRINT = "ab" * 32

SEPARATOR = "=" * 78
REPORT = f"""Проверка серверов vpncheck 1.0 (Xray 26.7.28)
Начало: 2026-10-16 23:00:00 +03:00, длилась 12.0 с
Компьютер: windows/amd64
Часы компьютера: сверены, поправка -2.5 с
Метка проверки в логах нод: vpncheck-0a1b2c3d

Итог: работает 1 из 2

{SEPARATOR}
Сервер: de1.example.net:443 — vless · grpc · reality — НЕ РАБОТАЕТ
Начало: 2026-10-16 23:00:00 +03:00, длилась 4.0 с
Время на ноде (UTC): 2026-10-16T20:00:00Z — 2026-10-16T20:00:05Z
Метка в логе ноды: vpncheck-0a1b2c3d-01.invalid
ОШИБКА     Пинг через сервер  нет ответа

{SEPARATOR}
Сервер: nl1.example.net:8443 — hysteria2 — РАБОТАЕТ
Начало: 2026-10-16 23:00:05 +03:00, длилась 3.0 с
Время на ноде (UTC): 2026-10-16T20:00:05Z — 2026-10-16T20:00:08Z
Метка в логе ноды: vpncheck-0a1b2c3d-02.invalid (не отправлена)
"""


# -- configuration ---------------------------------------------------------------------


def test_agents_are_read_as_the_agent_prints_them(caplog):
    raw = (
        f"de1=https://{TOKEN}@de1.example.net:7443#{FINGERPRINT}, "
        f"nl1=https://{TOKEN}@[2001:db8::1]:7443#{FINGERPRINT}\n"
        f"broken=http://{TOKEN}@x:1#{FINGERPRINT} nofp=https://{TOKEN}@x:1"
    )
    with caplog.at_level(logging.ERROR):
        agents = node_logs.parse_agents(raw)
    assert agents == [
        Agent("de1", "https://de1.example.net:7443", TOKEN, bytes.fromhex(FINGERPRINT)),
        Agent("nl1", "https://[2001:db8::1]:7443", TOKEN, bytes.fromhex(FINGERPRINT)),
    ]
    assert "broken" in caplog.text and "nofp" in caplog.text
    assert TOKEN not in caplog.text, "a bad entry is named, its token is not logged"
    assert node_logs.parse_agents("") == []


# -- the report ------------------------------------------------------------------------


def test_windows_come_out_of_the_report():
    windows, clock_checked = node_logs.parse_report(REPORT)
    assert clock_checked
    assert windows == [
        {"server": "de1.example.net:443", "from": "2026-10-16T20:00:00Z", "to": "2026-10-16T20:00:05Z",
         "marker": "vpncheck-0a1b2c3d-01.invalid", "failed": True},
        {"server": "nl1.example.net:8443", "from": "2026-10-16T20:00:05Z", "to": "2026-10-16T20:00:08Z",
         "marker": "vpncheck-0a1b2c3d-02.invalid", "failed": False},
    ]
    unchecked = REPORT.replace("Часы компьютера: сверены, поправка -2.5 с",
                               "Часы компьютера: не сверены, время на нодах указано по часам компьютера")
    windows, clock_checked = node_logs.parse_report(unchecked)
    query = node_logs.build_query(windows, clock_checked, ["u-1"])
    assert query["slack_seconds"] == node_logs.SLACK_UNCHECKED_CLOCK
    assert node_logs.build_query(windows, True, [])["slack_seconds"] == node_logs.SLACK_CHECKED_CLOCK
    assert node_logs.parse_report("no servers here") == ([], True)


def test_panel_names_include_the_legacy_one():
    request = {"remnawave_username": "u-abc", "remnawave_uuid": None, "telegram_id": 42}
    assert node_logs.panel_names(request) == ["u-abc", "42"]


# -- the agents ------------------------------------------------------------------------


@pytest.fixture
def certificate(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vpncheck-agent")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1)).not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_path, key_path)
    return context, cert.fingerprint(hashes.SHA256())


@pytest.fixture
async def agent_url(certificate):
    """A stand-in agent on loopback, behind its own self-signed certificate."""
    context, _ = certificate
    seen = []

    async def search(request):
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return web.Response(status=401, text="unauthorized")
        seen.append(await request.json())
        return web.json_response({"node": "de1", "files": [], "sections": [
            {"lines": ["line"], "attributed": True, "emails": ["u-1"], "addresses": ["198.51.100.7"]},
        ]})

    app = web.Application()
    app.router.add_post("/v1/search", search)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f"https://127.0.0.1:{port}", seen
    await runner.cleanup()


async def test_an_agent_is_reached_only_through_its_certificate(certificate, agent_url):
    url, seen = agent_url
    _, fingerprint = certificate
    good = Agent("de1", url, TOKEN, fingerprint)
    impostor = Agent("fake", url, TOKEN, bytes(32))
    wrong_token = Agent("old", url, "B" * 43, fingerprint)

    query = {"windows": [], "users": [], "slack_seconds": 5}
    answers = await node_logs.ask_agents([good, impostor, wrong_token], query, timeout=10)

    assert answers[0].result["sections"][0]["emails"] == ["u-1"] and not answers[0].error
    assert seen == [query], "only the agent with the right certificate was sent the query"
    assert "сертификат" in answers[1].error and answers[1].result is None
    assert answers[2].error.startswith("HTTP 401")


async def test_an_agent_that_is_down_is_an_answer_not_an_exception():
    nowhere = Agent("down", "https://127.0.0.1:9", TOKEN, bytes(32))
    [answer] = await node_logs.ask_agents([nowhere], {"windows": []}, timeout=5)
    assert answer.result is None and answer.error


# -- what the operators get -----------------------------------------------------------------


def query():
    windows, _ = node_logs.parse_report(REPORT)
    return node_logs.build_query(windows, True, ["u-1"])


def agent(name):
    return Agent(name, f"https://{name}:7443", TOKEN, bytes(32))


def test_render_names_what_each_node_found():
    answers = [
        Answer(agent("de1"), result={"files": [], "sections": [
            {"lines": ["2026/10/16 20:00:01 from 198.51.100.7:1 accepted tcp:x:80 email: u-1"],
             "attributed": True, "emails": ["u-1"], "addresses": ["198.51.100.7"]},
            {"lines": []},
        ]}),
        Answer(agent("nl<1>"), result={"files": [{"path": "/var/log/remnanode/access.log", "error": "no such file"}],
                                      "sections": [{"lines": ["REALITY: invalid"], "attributed": False}, {"lines": []}]}),
        Answer(agent("fi1"), error="не ответил за 90 с"),
    ]
    data, caption = node_logs.render(7, "Не работает", query(), answers)
    text = data.decode()

    assert "Нода de1: ответила" in text
    assert "Нода nl<1>: ответила, но не читает: /var/log/remnanode/access.log (no such file)" in text
    assert "Нода fi1: не ответила — не ответил за 90 с" in text
    assert "-- нода de1: пользователь u-1, адрес 198.51.100.7\n2026/10/16 20:00:01 from" in text
    assert "-- нода nl<1>: метки нет" in text
    # The second server worked and no node has its marker.
    assert "проверьте, что access-лог Xray включён" in text
    assert caption == "🖥 Логи нод по проверке в <b>#7</b>: строки клиента нашлись на de1; не ответили: fi1"

    _, caption = node_logs.render(7, "x", query(), [Answer(agent("a&b"), error="x")])
    assert caption.endswith("строк клиента не нашлось; не ответили: a&amp;b")


# -- the job ---------------------------------------------------------------------------------


class FakeSupport:
    def __init__(self):
        self.data = {"att-1": REPORT.encode()}
        self.telegram = []

    async def attachment_data(self, attachment_id):
        return self.data.get(attachment_id)

    async def card_for(self, ticket_id, chat_id):
        return {ADMIN: 501, OTHER: 502}[chat_id]

    async def record_telegram_message(self, chat_id, telegram_message_id, ticket_id, kind, **_):
        self.telegram.append((chat_id, telegram_message_id, ticket_id, kind))


class FakeDiagnostics:
    def __init__(self, requests):
        self.requests = requests
        self.marked = []

    async def pending_node_logs(self):
        return [r for r in self.requests if r["id"] not in self.marked]

    async def mark_node_logs(self, request_id):
        self.marked.append(request_id)


class FakeBot:
    def __init__(self, refuse=()):
        self.documents = []
        self.refuse = refuse

    async def send_document(self, chat_id, document, **kwargs):
        if chat_id in self.refuse:
            from aiogram.exceptions import TelegramForbiddenError
            from aiogram.methods import SendMessage
            raise TelegramForbiddenError(method=SendMessage(chat_id=chat_id, text="x"), message="Forbidden: bot was blocked")
        self.documents.append({"chat_id": chat_id, "document": document, **kwargs})
        return SimpleNamespace(message_id=900 + len(self.documents))


def request(**changes):
    return {"id": 3, "ticket_id": 7, "subject": "Не работает", "attachment_id": "att-1",
            "telegram_id": 42, "remnawave_username": "u-1", "remnawave_uuid": None, **changes}


@pytest.fixture
def repos(monkeypatch):
    support = FakeSupport()
    monkeypatch.setattr(job, "_support", support)
    monkeypatch.setattr(job.settings, "admin_ids_raw", f"{ADMIN} {OTHER}")
    return support


async def test_node_logs_reach_every_admin_chat_on_the_ticket_card(monkeypatch, repos):
    diagnostics = FakeDiagnostics([request()])
    monkeypatch.setattr(job, "_diagnostics", diagnostics)
    asked = []

    async def ask(agents, query):
        asked.append(query)
        return [Answer(agents[0], result={"files": [], "sections": [
            {"lines": ["found"], "attributed": True, "emails": ["u-1"], "addresses": []}, {"lines": []},
        ]})]

    monkeypatch.setattr(job, "ask_agents", ask)
    bot = FakeBot(refuse={OTHER})
    await job.run_pass(bot, [agent("de1")])

    [query_sent] = asked
    assert [w["marker"] for w in query_sent["windows"]] == ["vpncheck-0a1b2c3d-01.invalid", "vpncheck-0a1b2c3d-02.invalid"]
    assert query_sent["users"] == ["u-1", "42"]
    [sent] = bot.documents
    assert sent["chat_id"] == ADMIN and sent["reply_parameters"].message_id == 501
    assert sent["document"].filename == "node-logs-7.txt" and b"found" in sent["document"].data
    assert "нашлись на de1" in sent["caption"]
    assert repos.telegram == [(ADMIN, 901, 7, "notice")]
    assert diagnostics.marked == [3]

    await job.run_pass(bot, [agent("de1")])
    assert len(asked) == 1, "a report is looked up once"


async def test_a_report_with_nothing_to_look_for_is_marked_without_asking(monkeypatch, repos):
    diagnostics = FakeDiagnostics([request(attachment_id=None), request(id=4, attachment_id="purged")])
    monkeypatch.setattr(job, "_diagnostics", diagnostics)

    async def ask(*_):
        raise AssertionError("no agent should be asked")

    monkeypatch.setattr(job, "ask_agents", ask)
    bot = FakeBot()
    await job.run_pass(bot, [agent("de1")])
    assert diagnostics.marked == [3, 4] and bot.documents == []

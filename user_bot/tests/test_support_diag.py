"""
The customer's answer to a request for a server-check report.

What is pinned: only the ticket's owner can answer, an answer is final, a
yes hands over a code and where to get the program, a no hands over nothing,
and a stale question says so instead of taking an answer.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.support_diag as diag
from tgvpn_shared.support_diagnostics import hash_code, normalize_code

OWNER = 555


class FakeCallback:
    def __init__(self, data: str, user_id: int = OWNER):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.alerts: list[tuple[str | None, bool]] = []
        self.edited: list[str] = []
        self.markup_cleared = False
        self.message = SimpleNamespace(
            edit_text=self._edit, edit_reply_markup=self._clear, answer=AsyncMock(),
        )

    async def answer(self, text: str | None = None, show_alert: bool = False, **_):
        self.alerts.append((text, show_alert))

    async def _edit(self, text, **kwargs):
        assert kwargs.get("parse_mode") == "HTML" and kwargs.get("reply_markup") is None
        self.edited.append(text)

    async def _clear(self, **_):
        self.markup_cleared = True


def request(**overrides) -> dict:
    row = dict(id=9, ticket_id=7, decision=None, fresh=True, status="open", subject="Не работает", telegram_id=OWNER)
    row.update(overrides)
    return row


@pytest.fixture
def repo(monkeypatch):
    fake = SimpleNamespace(
        get=AsyncMock(return_value=request()),
        grant=AsyncMock(return_value=1_800_000_000),
        decline=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(diag, "_diagnostics", fake)
    monkeypatch.setattr(diag.get_settings(), "vpncheck_download_url", "https://example.com/vpncheck/")
    return fake


async def test_a_yes_gives_the_owner_a_code_and_the_download_link(repo):
    callback = FakeCallback("diag:allow:9")
    await diag.allow(callback)

    [(request_id, stored_hash, _ttl)] = [call.args for call in repo.grant.await_args_list]
    assert request_id == 9
    [text] = callback.edited
    assert "https://example.com/vpncheck/" in text
    code = text.split("<code>")[1].split("</code>")[0]
    assert normalize_code(code) and hash_code(code) == stored_hash


async def test_a_no_records_it_and_shows_no_code(repo):
    callback = FakeCallback("diag:deny:9")
    await diag.deny(callback)

    repo.decline.assert_awaited_once_with(9)
    repo.grant.assert_not_awaited()
    assert "отказались" in callback.edited[0] and "<code>" not in callback.edited[0]


@pytest.mark.parametrize("handler", [diag.allow, diag.deny])
async def test_nobody_else_can_answer_for_the_owner(repo, handler):
    callback = FakeCallback("diag:allow:9", user_id=999)
    await handler(callback)

    assert callback.alerts == [("Этот запрос не для вас.", True)]
    repo.grant.assert_not_awaited()
    repo.decline.assert_not_awaited()
    assert callback.edited == []


async def test_an_answered_question_only_loses_its_buttons(repo):
    repo.get.return_value = request(decision="granted")
    callback = FakeCallback("diag:deny:9")
    await diag.deny(callback)

    repo.decline.assert_not_awaited()
    assert callback.markup_cleared and callback.edited == []


@pytest.mark.parametrize("stale", [dict(fresh=False), dict(status="closed")])
async def test_a_stale_question_says_so(repo, stale):
    repo.get.return_value = request(**stale)
    callback = FakeCallback("diag:allow:9")
    await diag.allow(callback)

    repo.grant.assert_not_awaited()
    assert "больше не действует" in callback.edited[0]


async def test_a_race_lost_to_another_tap_hands_out_no_code(repo):
    repo.grant.return_value = None
    callback = FakeCallback("diag:allow:9")
    await diag.allow(callback)

    assert callback.edited == [] and callback.markup_cleared


async def test_without_a_download_link_nothing_is_granted(repo, monkeypatch):
    monkeypatch.setattr(diag.get_settings(), "vpncheck_download_url", "")
    callback = FakeCallback("diag:allow:9")
    await diag.allow(callback)

    repo.grant.assert_not_awaited()
    assert callback.alerts[0][1] is True

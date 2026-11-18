"""
The referral screens, from «🎁 Реф. программа» in the menu and from /ref.

Telegram refuses a MarkdownV2 message with one bare reserved character in it,
and the user sees a button that does nothing. That is what happened to
everyone who had named a referrer: a hand-written `\\.` inside text that was
escaped again came out as an escaped backslash and a bare dot.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.referrals as referrals

RESERVED = set("_*[]()~`>#+-=|{}.!")


def bare_reserved(text: str, *, markup: str = "") -> list[str]:
    """Reserved characters with no backslash before them, except `markup`."""
    bare, i = [], 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] in RESERVED and text[i] not in markup:
            bare.append(text[max(0, i - 12) : i + 1])
        i += 1
    return bare


def _sent_text(answer: AsyncMock) -> str:
    args, kwargs = answer.await_args
    return kwargs.get("text") or args[0]


async def _press_button(monkeypatch, row):
    monkeypatch.setattr(
        referrals, "_users", SimpleNamespace(get_user_by_id=AsyncMock(return_value=row))
    )
    message = SimpleNamespace(answer=AsyncMock())
    cb = SimpleNamespace(answer=AsyncMock(), from_user=SimpleNamespace(id=42), message=message)
    await referrals.referral_program_button(cb, SimpleNamespace(clear=AsyncMock()))
    cb.answer.assert_awaited_once()
    referrals._users.get_user_by_id.assert_awaited_once_with(42)
    return message.answer


@pytest.mark.parametrize(
    "row",
    [
        {"referred_people": 3, "referrer_tag": "some_friend"},
        {"referred_people": 0, "referrer_tag": None},
        None,  # no profile yet
    ],
    ids=["with referrer", "without referrer", "no profile"],
)
async def test_the_menu_button_sends_valid_markdown(monkeypatch, row):
    answer = await _press_button(monkeypatch, row)
    assert answer.await_args.kwargs["parse_mode"] == "MarkdownV2"
    assert bare_reserved(_sent_text(answer)) == []


async def test_with_a_referrer_the_count_reads_normally(monkeypatch):
    answer = await _press_button(monkeypatch, {"referred_people": 3, "referrer_tag": "some_friend"})
    text = _sent_text(answer)
    assert "Ты уже пригласил: 3 чел\\." in text
    assert "\\\\" not in text  # no escaped backslash shown to the user
    assert "@some\\_friend" in text


async def test_the_discounts_screen_has_a_bold_heading_and_nothing_bare():
    message = SimpleNamespace(answer=AsyncMock())
    cb = SimpleNamespace(answer=AsyncMock(), message=message)

    await referrals.referral_info(cb)

    text = _sent_text(message.answer)
    assert text.startswith("🎁 *Реферальная программа*")
    assert bare_reserved(text, markup="*") == []
    assert text.count("*") - text.count("\\*") == 2

"""
The referral screens: «🎁 Реферальная программа» (how it works, opened from
the menu, /ref and old buttons) and «👥 Мои приглашения» (who invited you,
whom you invited, what your next friend is worth).

Both are HTML. The old screen was MarkdownV2 and broke on one unescaped dot:
Telegram refused the message and the button did nothing.
"""

from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.referrals as referrals
from handlers.constants import PRICES
from handlers.keyboards import REFERRAL_INVITES_CALLBACK


class _Tags(HTMLParser):
    """Collects tags, failing on anything Telegram's HTML mode would refuse."""

    ALLOWED = {"b", "code"}

    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        assert tag in self.ALLOWED, tag
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, tag


def assert_valid_html(text: str) -> None:
    parser = _Tags()
    parser.feed(text)
    parser.close()
    assert parser.stack == []


def _row(**fields):
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "telegram_tag": "me",
        "email": "",
        "referrer_tag": None,
        "referred_people": 0,
    }
    row.update(fields)
    return row


def _invitee(tag, credited):
    return {"telegram_tag": tag, "is_referred": credited}


def _buttons(markup):
    return [b.callback_data for r in markup.inline_keyboard for b in r]


# -- «🎁 Реферальная программа» ---------------------------------------------


def test_the_overview_explains_the_programme_and_the_price_ladder():
    text = referrals.overview_html("me")
    assert_valid_html(text)
    assert "Как это работает" in text
    assert "Указать пригласившего" in text
    for tier in range(6):
        assert f"— {PRICES[tier][1]} ₽/мес" in text
    assert "5 и больше — 9 ₽/мес" in text
    assert "<code>@me</code>" in text


def test_without_a_telegram_username_it_says_how_to_get_one():
    text = referrals.overview_html(None)
    assert_valid_html(text)
    assert "Имя пользователя" in text
    assert "<code>@" not in text


async def _press(monkeypatch, handler, row, *, data="referral", invitees=()):
    repo = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=row),
        list_invitees=AsyncMock(return_value=list(invitees)),
    )
    monkeypatch.setattr(referrals, "_users", repo)
    message = SimpleNamespace(text="menu", edit_text=AsyncMock(), answer=AsyncMock())
    cb = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        message=message,
        from_user=SimpleNamespace(id=42, username="me"),
    )
    if handler is referrals.referral_invites:
        await handler(cb)
    else:
        await handler(cb, SimpleNamespace(clear=AsyncMock()))
    cb.answer.assert_awaited_once()
    return repo, message


@pytest.mark.parametrize(
    "row, can_set",
    [
        (_row(), True),
        (_row(referrer_tag="friend"), False),
        (None, False),  # no profile yet: nothing to attach a referrer to
    ],
    ids=["no referrer", "has referrer", "no profile"],
)
async def test_the_menu_button_opens_the_overview_in_place(monkeypatch, row, can_set):
    _, message = await _press(monkeypatch, referrals.referral_program_button, row)

    kwargs = message.edit_text.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert "Реферальная программа" in message.edit_text.await_args.args[0]
    buttons = _buttons(kwargs["reply_markup"])
    assert buttons[0] == REFERRAL_INVITES_CALLBACK
    assert ("referral_set_tag" in buttons) is can_set
    assert buttons[-1] == "main_menu"


async def _handler_for(data: str):
    cb = SimpleNamespace(data=data)
    for handler in referrals.router.callback_query.handlers:
        results = [await f.call(cb) for f in handler.filters or []]
        if all(results):
            return handler.callback
    return None


@pytest.mark.parametrize("data", ["referral", "referral_info"])
async def test_old_buttons_open_the_same_screen(data):
    """`referral_info` is the retired «О скидках» and the reminder's «Моя ссылка»."""
    assert await _handler_for(data) is referrals.referral_program_button


# -- «👥 Мои приглашения» -----------------------------------------------------


async def test_invitations_list_who_named_you_and_their_status(monkeypatch):
    row = _row(referrer_tag="friend", referred_people=2, email="me@example.com")
    invitees = [_invitee("anna", True), _invitee("max_k", True), _invitee("den", False)]

    repo, message = await _press(
        monkeypatch, referrals.referral_invites, row, invitees=invitees
    )

    repo.list_invitees.assert_awaited_once_with(
        telegram_tag="me",
        email="me@example.com",
        exclude_user_id=row["id"],
        limit=referrals.INVITEES_SHOWN + 1,
    )
    text = message.edit_text.await_args.args[0]
    assert_valid_html(text)
    assert "Тебя пригласил: @friend" in text
    assert text.index("✅ @anna — засчитано") < text.index("⏳ @den — ждём первую оплату")
    assert "Засчитано: 2" in text
    assert f"Твоя цена: {PRICES[2][1]} ₽/мес" in text
    assert f"Ещё один друг — и будет {PRICES[3][1]} ₽/мес" in text
    assert _buttons(message.edit_text.await_args.kwargs["reply_markup"]) == ["referral"]


def test_nobody_yet_and_no_referrer_read_plainly():
    text = referrals.invites_html(_row(), [], more=False)
    assert_valid_html(text)
    assert "Тебя пригласил: никто" in text
    assert "Пока никто не указал тебя пригласившим" in text


def test_a_website_invitee_without_a_tag_is_still_listed():
    text = referrals.invites_html(_row(), [_invitee("", False)], more=False)
    assert "⏳ аккаунт с сайта — ждём первую оплату" in text


def test_a_long_list_says_there_are_more():
    text = referrals.invites_html(_row(), [_invitee("a", True)], more=True)
    assert "…и другие" in text


@pytest.mark.parametrize("credited", [5, 9])
def test_at_the_top_tier_there_is_no_next_price(credited):
    text = referrals.invites_html(_row(referred_people=credited), [], more=False)
    assert f"Твоя цена: {PRICES[5][1]} ₽/мес" in text
    assert "максимальная скидка" in text
    assert "Ещё один друг" not in text


def test_tags_cannot_inject_markup():
    text = referrals.invites_html(
        _row(referrer_tag="<b>x"), [_invitee("<i>y", True)], more=False
    )
    assert_valid_html(text)
    assert "&lt;b&gt;x" in text


async def test_without_a_profile_invitations_point_to_start(monkeypatch):
    _, message = await _press(monkeypatch, referrals.referral_invites, None)
    assert "/start" in message.answer.await_args.args[0]

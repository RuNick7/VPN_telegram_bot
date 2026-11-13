"""
Custom emoji icons on buttons: the icon table, the swap, and what happens when
Telegram will not take them.
"""

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe, SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import button_icons
import make_emoji_pack
from button_icons import (
    ICON_DIR,
    ICONS,
    ButtonIconsMiddleware,
    apply_icons,
    normalize,
    split_leading_emoji,
)

USER_BOT = Path(__file__).resolve().parent.parent


# -- the table ---------------------------------------------------------------


def test_one_icon_per_emoji_and_one_emoji_per_icon():
    """Matching the set by emoji only works if neither side repeats."""
    emoji = [normalize(e) for e, _ in ICONS]
    files = [f for _, f in ICONS]
    assert len(set(emoji)) == len(emoji)
    assert len(set(files)) == len(files)


def test_every_icon_file_is_a_100px_png():
    entries = make_emoji_pack.plan(ICON_DIR)
    assert len(entries) == len(ICONS) == 31


def test_the_icons_carry_their_licence():
    assert "MIT License" in (ICON_DIR / "LICENSE").read_text()


def _button_texts() -> list[str]:
    texts = []
    for path in USER_BOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        for match in re.finditer(r'InlineKeyboardButton\(\s*text="([^"]*)"', path.read_text()):
            texts.append(match.group(1))
    return texts


def test_every_emoji_on_a_button_has_an_icon():
    """A new button with an emoji nobody drew would stay the odd one out."""
    unknown = []
    for text in _button_texts():
        first = text[:1]
        if not first or first.isalnum() or first in "{«(":
            continue  # no emoji to replace
        if split_leading_emoji(text) is None:
            unknown.append(text)
    assert unknown == []


# -- the swap ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("🚀 Подключиться", ("🚀", "Подключиться")),
        ("✍️ Указать пригласившего", ("✍", "Указать пригласившего")),
        ("✍ Указать пригласившего", ("✍", "Указать пригласившего")),
        ("ℹ️ О скидках", ("ℹ", "О скидках")),
        ("🖥 Windows", ("🖥", "Windows")),
        ("iPhone", None),
        ("🚀", None),  # nothing left to show as text
        ("🦄 Что-то новое", None),
    ],
)
def test_leading_emoji_is_split_off(text, expected):
    assert split_leading_emoji(text) == expected


def _markup(*buttons) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])


def test_known_emoji_become_icons_and_leave_the_text():
    original = _markup(
        InlineKeyboardButton(text="🚀 Подключиться", callback_data="connect", style="success"),
        InlineKeyboardButton(text="Не сейчас", callback_data="later"),
    )
    iconed = apply_icons(original, {"🚀": "111"})

    first, second = iconed.inline_keyboard[0][0], iconed.inline_keyboard[1][0]
    assert (first.text, first.icon_custom_emoji_id) == ("Подключиться", "111")
    assert (first.callback_data, first.style) == ("connect", "success")
    assert (second.text, second.icon_custom_emoji_id) == ("Не сейчас", None)
    # The keyboard the handler built is not touched.
    assert original.inline_keyboard[0][0].text == "🚀 Подключиться"


def test_nothing_to_change_returns_none():
    markup = _markup(InlineKeyboardButton(text="🚀 Подключиться", callback_data="connect"))
    assert apply_icons(markup, {}) is None
    assert apply_icons(markup, {"🎁": "222"}) is None


def test_a_button_that_already_has_an_icon_keeps_it():
    markup = _markup(
        InlineKeyboardButton(text="🚀 Мой", callback_data="x", icon_custom_emoji_id="999")
    )
    assert apply_icons(markup, {"🚀": "111"}) is None


# -- the middleware ----------------------------------------------------------


def _bot(stickers=None, error=None):
    get_sticker_set = AsyncMock()
    if error:
        get_sticker_set.side_effect = error
    else:
        get_sticker_set.return_value = SimpleNamespace(stickers=stickers or [])
    return SimpleNamespace(get_sticker_set=get_sticker_set)


def _sticker(emoji, custom_emoji_id):
    return SimpleNamespace(emoji=emoji, custom_emoji_id=custom_emoji_id)


def _send() -> SendMessage:
    return SendMessage(
        chat_id=1,
        text="Меню",
        reply_markup=_markup(InlineKeyboardButton(text="🚀 Подключиться", callback_data="connect")),
    )


def _sent_button(make_request, call=-1):
    return make_request.await_args_list[call].args[1].reply_markup.inline_keyboard[0][0]


async def test_icons_go_out_with_the_message():
    bot = _bot([_sticker("🚀", "111"), _sticker("✍️", "222")])
    make_request = AsyncMock(return_value="ok")

    assert await ButtonIconsMiddleware("kaira_icons_by_bot")(make_request, bot, _send()) == "ok"

    button = _sent_button(make_request)
    assert (button.text, button.icon_custom_emoji_id) == ("Подключиться", "111")
    bot.get_sticker_set.assert_awaited_once_with(name="kaira_icons_by_bot")


async def test_the_set_is_read_once():
    bot = _bot([_sticker("🚀", "111")])
    middleware = ButtonIconsMiddleware("kaira_icons_by_bot")
    for _ in range(3):
        await middleware(AsyncMock(), bot, _send())
    bot.get_sticker_set.assert_awaited_once()


async def test_without_a_set_nothing_changes():
    bot = _bot([_sticker("🚀", "111")])
    make_request = AsyncMock()

    await ButtonIconsMiddleware("")(make_request, bot, _send())

    assert _sent_button(make_request).text == "🚀 Подключиться"
    bot.get_sticker_set.assert_not_awaited()


async def test_requests_without_a_keyboard_pass_straight_through():
    bot = _bot([_sticker("🚀", "111")])
    make_request = AsyncMock()
    method = GetMe()

    await ButtonIconsMiddleware("kaira_icons_by_bot")(make_request, bot, method)

    make_request.assert_awaited_once_with(bot, method)
    bot.get_sticker_set.assert_not_awaited()


async def test_an_unreadable_set_means_plain_emoji_not_a_failure():
    bot = _bot(error=RuntimeError("no such set"))
    make_request = AsyncMock()

    await ButtonIconsMiddleware("kaira_icons_by_bot")(make_request, bot, _send())

    assert _sent_button(make_request).text == "🚀 Подключиться"


async def test_an_unreadable_set_is_not_asked_for_on_every_message(monkeypatch):
    bot = _bot(error=RuntimeError("no such set"))
    middleware = ButtonIconsMiddleware("kaira_icons_by_bot")
    clock = [1000.0]
    monkeypatch.setattr(button_icons.time, "monotonic", lambda: clock[0])

    await middleware(AsyncMock(), bot, _send())
    await middleware(AsyncMock(), bot, _send())
    assert bot.get_sticker_set.await_count == 1

    clock[0] += button_icons.RETRY_SECONDS + 1
    await middleware(AsyncMock(), bot, _send())
    assert bot.get_sticker_set.await_count == 2


async def test_refused_icons_are_dropped_and_the_message_still_goes():
    bot = _bot([_sticker("🚀", "111")])
    refusal = TelegramBadRequest(method=_send(), message="Bad Request: invalid custom emoji")
    make_request = AsyncMock(side_effect=[refusal, "ok"])
    middleware = ButtonIconsMiddleware("kaira_icons_by_bot")

    assert await middleware(make_request, bot, _send()) == "ok"
    assert _sent_button(make_request, call=1).text == "🚀 Подключиться"
    assert middleware.disabled

    # And from then on, no icons at all.
    later = AsyncMock()
    await middleware(later, bot, _send())
    assert _sent_button(later).text == "🚀 Подключиться"


async def test_an_error_that_is_not_about_icons_is_raised_and_icons_stay():
    bot = _bot([_sticker("🚀", "111")])
    error = TelegramBadRequest(method=_send(), message="Bad Request: message is not modified")
    make_request = AsyncMock(side_effect=[error, error])
    middleware = ButtonIconsMiddleware("kaira_icons_by_bot")

    with pytest.raises(TelegramBadRequest):
        await middleware(make_request, bot, _send())
    assert not middleware.disabled


# -- the pack script ---------------------------------------------------------


def test_set_names_follow_telegrams_rule():
    assert make_emoji_pack.set_name("kaira_icons", "kaira_bot") == "kaira_icons_by_kaira_bot"
    for bad in ("1icons", "kaira__icons", "kaira-icons", ""):
        with pytest.raises(SystemExit):
            make_emoji_pack.set_name(bad, "kaira_bot")


def test_a_missing_or_wrong_size_image_stops_the_upload(tmp_path):
    with pytest.raises(SystemExit) as exc:
        make_emoji_pack.plan(tmp_path)
    assert "rocket-launch.png" in str(exc.value)

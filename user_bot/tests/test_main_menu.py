"""
The main menu: four buttons, two of them coloured, and the one-time channel
invitation in front of it.

The invitation is not a gate. «Я подписался» opens the menu whether or not
the customer actually subscribed -- nothing asks Telegram -- and the
invitation is shown once per account, ever.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.menu as menu
from handlers.keyboards import BLUE, GREEN, RED, main_menu_keyboard

DAY = 86400
NOW = 10_000_000


def row(*, subscription_ends: int = NOW + 30 * DAY, channel_prompt_shown: bool = True) -> dict:
    return {
        "id": "row-uuid",
        "email": "x@example.com",  # short-circuits the email-bonus offer
        "trial_link_granted": True,
        "bonus_offer_shown_in_bot": True,
        "bonus_offer_dismissed": True,
        "channel_prompt_shown": channel_prompt_shown,
        "subscription_ends": subscription_ends,
    }


class FakeMessage:
    """Just enough of a `types.Message` for `_render_main_menu`."""

    def __init__(self, user_id: int = 555):
        self.chat = SimpleNamespace(id=1)
        self.from_user = SimpleNamespace(id=user_id, username="tester")
        self.sent: list[dict] = []

        async def send_message(chat_id, text, **kwargs):
            self.sent.append({"chat_id": chat_id, "text": text, **kwargs})
            return SimpleNamespace()

        self.bot = SimpleNamespace(send_message=send_message)

    @property
    def last(self) -> dict:
        return self.sent[-1]


@pytest.fixture
def repo(monkeypatch):
    fake = SimpleNamespace(
        user_in_db=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(),
        update_telegram_tag=AsyncMock(),
        mark_channel_prompt_shown=AsyncMock(),
    )
    monkeypatch.setattr(menu, "_users", fake)
    monkeypatch.setattr(menu, "get_settings", lambda: SimpleNamespace(lte_enabled=False))
    monkeypatch.setattr(menu.time, "time", lambda: NOW)
    monkeypatch.setattr(menu, "STATUS_CHANNEL_URL", "https://t.me/KairaVPN_Channel")
    return fake


def _buttons(keyboard) -> list:
    return [b for r in keyboard.inline_keyboard for b in r]


def _by_callback(keyboard, data: str):
    return next(b for b in _buttons(keyboard) if b.callback_data == data)


# -- layout and colours ------------------------------------------------------


def test_the_menu_is_connect_renew_then_referral_and_help():
    rows = main_menu_keyboard().inline_keyboard
    assert [[b.callback_data for b in r] for r in rows] == [
        ["connect"],
        ["renew_menu"],
        ["referral", "help"],
    ]


def test_connect_is_green_and_renew_is_blue_normally():
    keyboard = main_menu_keyboard(renew_urgent=False)
    assert _by_callback(keyboard, "connect").style == GREEN
    assert _by_callback(keyboard, "renew_menu").style == BLUE
    assert _by_callback(keyboard, "referral").style is None
    assert _by_callback(keyboard, "help").style is None


def test_renew_turns_red_when_it_matters():
    assert _by_callback(main_menu_keyboard(renew_urgent=True), "renew_menu").style == RED


@pytest.mark.parametrize(
    "ends, style",
    [
        (NOW + 30 * DAY, BLUE),
        (NOW + 4 * DAY, BLUE),
        (NOW + 3 * DAY, RED),
        (NOW + 1 * DAY, RED),
        (NOW - 2 * DAY, RED),  # expired, still inside the free grace window
    ],
)
async def test_renew_colour_follows_the_days_left(repo, ends, style):
    repo.get_user_by_id.return_value = row(subscription_ends=ends)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert _by_callback(msg.last["reply_markup"], "renew_menu").style == style


async def test_the_menu_no_longer_asks_for_a_device(repo):
    repo.get_user_by_id.return_value = row()
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "Выберите своё устройство" not in msg.last["text"]
    assert "Действует до" in msg.last["text"]


# -- the channel invitation --------------------------------------------------


async def test_the_invitation_comes_before_the_first_menu(repo):
    repo.get_user_by_id.return_value = row(channel_prompt_shown=False)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert len(msg.sent) == 1
    sent = msg.last
    assert "Подпишитесь" in sent["text"]
    buttons = _buttons(sent["reply_markup"])
    assert buttons[0].url == "https://t.me/KairaVPN_Channel"
    assert buttons[1].callback_data == "channel_ok"
    repo.mark_channel_prompt_shown.assert_awaited_once_with("row-uuid")


def test_the_invitation_says_what_the_channel_is_for():
    text = menu.CHANNEL_PROMPT_HTML
    assert "редко" in text
    assert "Рекламы в канале нет" in text
    assert "важных изменениях" in text


async def test_the_invitation_is_shown_once(repo):
    repo.get_user_by_id.return_value = row(channel_prompt_shown=True)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "Подпишитесь" not in msg.last["text"]
    assert "connect" in [b.callback_data for b in _buttons(msg.last["reply_markup"])]
    repo.mark_channel_prompt_shown.assert_not_awaited()


async def test_without_a_channel_there_is_no_invitation(repo, monkeypatch):
    monkeypatch.setattr(menu, "STATUS_CHANNEL_URL", "")
    repo.get_user_by_id.return_value = row(channel_prompt_shown=False)
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "Подпишитесь" not in msg.last["text"]


async def test_a_failed_write_shows_the_menu_rather_than_nothing(repo):
    repo.get_user_by_id.return_value = row(channel_prompt_shown=False)
    repo.mark_channel_prompt_shown.side_effect = RuntimeError("db down")
    msg = FakeMessage()

    await menu._render_main_menu(msg)

    assert "connect" in [b.callback_data for b in _buttons(msg.last["reply_markup"])]


async def test_i_subscribed_opens_the_menu_without_checking(monkeypatch):
    """Taken at its word: the handler never asks Telegram about membership."""
    render = AsyncMock()
    monkeypatch.setattr(menu, "_render_main_menu", render)
    cb = SimpleNamespace(
        message=SimpleNamespace(delete=AsyncMock()),
        bot=SimpleNamespace(),  # no get_chat_member to call, by construction
    )

    await menu.channel_ok_cb(cb)

    cb.message.delete.assert_awaited_once()
    render.assert_awaited_once_with(cb, greeting="Привет")


async def test_the_menu_after_the_invitation_greets_rather_than_welcomes_back(repo):
    repo.get_user_by_id.return_value = row()
    msg = FakeMessage()

    await menu._render_main_menu(msg, greeting="Привет")

    assert msg.last["text"].startswith("<b>👋 Привет, @tester!</b>")


# -- the screens behind the buttons ------------------------------------------


async def test_connect_opens_the_device_picker_in_place():
    message = SimpleNamespace(text="menu", edit_text=AsyncMock(), answer=AsyncMock())
    cb = SimpleNamespace(message=message, answer=AsyncMock())
    state = SimpleNamespace(clear=AsyncMock())

    await menu.connect_cb(cb, state)

    message.edit_text.assert_awaited_once()
    keyboard = message.edit_text.await_args.kwargs["reply_markup"]
    assert any(b.callback_data == "os:ios" for b in _buttons(keyboard))


async def test_connect_from_a_video_sends_the_picker_anew():
    """A video caption cannot be edited into a text message."""
    message = SimpleNamespace(text=None, edit_text=AsyncMock(), answer=AsyncMock())
    cb = SimpleNamespace(message=message, answer=AsyncMock())

    await menu.connect_cb(cb, SimpleNamespace(clear=AsyncMock()))

    message.edit_text.assert_not_awaited()
    message.answer.assert_awaited_once()


async def test_help_button_sends_the_help_screen_not_a_toast():
    """`CallbackQuery.answer(text)` would only flash a notification."""
    message = SimpleNamespace(text="menu", edit_text=AsyncMock(), answer=AsyncMock())
    cb = SimpleNamespace(message=message, answer=AsyncMock())

    await menu.help_cb(cb)

    cb.answer.assert_awaited_once_with()
    message.edit_text.assert_awaited_once()
    assert "Помощь" in message.edit_text.await_args.args[0]

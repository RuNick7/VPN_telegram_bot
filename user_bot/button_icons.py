"""
Custom emoji icons on the bot's inline buttons.

Every button keeps an ordinary emoji at the start of its text -- that is what
the code says and what old Telegram releases show. When `BUTTON_ICONS_SET`
names a custom emoji set, a request middleware swaps that leading emoji for
the set's matching icon (`icon_custom_emoji_id`) on the way out, so one place
covers every keyboard the bot sends, including ones written later.

The set is matched by emoji, not by position: each icon in it carries, as its
emoji, the ordinary emoji of the buttons it replaces (🚀 for «Подключиться»,
🔙 for every «Назад»…). A pack drawn later replaces this one by tagging its
images the same way and changing `BUTTON_ICONS_SET` -- no code, no ids.

Bots may put custom emoji on buttons only when their owner has Telegram
Premium (Bot API 9.4). If Telegram refuses a message because of the icons, it
is sent again without them and icons are switched off until restart: a menu
without icons is fine, a menu that does not arrive is not.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

ICON_DIR = Path(__file__).resolve().parent / "data" / "button_icons"

# The temporary pack: Phosphor Icons (MIT), Regular weight, white on
# transparent, 100x100 -- see data/button_icons/LICENSE. Each entry is the
# ordinary emoji the buttons carry and the file drawn for it. One emoji per
# icon and one icon per emoji: that is what makes matching by emoji work.
ICONS: list[tuple[str, str]] = [
    # devices
    ("🍎", "apple-logo"),
    ("🤖", "android-logo"),
    ("🖥", "windows-logo"),
    ("💻", "laptop"),
    ("🐧", "linux-logo"),
    ("📺", "television"),
    ("🍏", "television-simple"),
    # main menu
    ("🚀", "rocket-launch"),
    ("💳", "credit-card"),
    ("🎁", "gift"),
    ("❓", "question"),
    # everything else
    ("🔙", "arrow-left"),
    ("❌", "x"),
    ("📧", "envelope-simple"),
    ("🩺", "stethoscope"),
    ("📢", "megaphone"),
    ("✅", "check-circle"),
    ("📶", "cell-signal-full"),
    ("✍️", "pencil-simple"),
    ("ℹ️", "info"),
    ("🛠", "headset"),
    ("📖", "book-open"),
    ("📄", "file-text"),
    ("📲", "download-simple"),
    ("🔍", "magnifying-glass"),
    ("😕", "warning"),
    ("📱", "device-mobile"),
    ("🔄", "arrows-clockwise"),
    ("📋", "list"),
    ("🔗", "link"),
    ("🌐", "globe"),
]

# How long to wait before asking Telegram for the set again after a failure.
RETRY_SECONDS = 600

_VS16 = "️"


def normalize(emoji: str) -> str:
    """
    Compare emoji without the emoji-presentation selector.

    Telegram may hand back «✍» for a sticker tagged «✍️» or the other way
    round; the selector changes how a glyph is drawn, not which one it is.
    """
    return emoji.replace(_VS16, "")


_KNOWN = sorted({normalize(e) for e, _ in ICONS}, key=len, reverse=True)


def split_leading_emoji(text: str) -> tuple[str, str] | None:
    """
    `("🚀", "Подключиться")` for "🚀 Подключиться", or None.

    Only emoji this module knows are recognised, so a button that starts with
    anything else -- a price, a device name -- is never touched.
    """
    head = text.lstrip()
    norm = normalize(head)
    for emoji in _KNOWN:
        if not norm.startswith(emoji):
            continue
        # Step over the emoji in the original text, selectors included.
        i = seen = 0
        while seen < len(emoji) and i < len(head):
            if head[i] != _VS16:
                seen += 1
            i += 1
        rest = head[i:].lstrip(_VS16).strip()
        if rest:
            return emoji, rest
    return None


def apply_icons(
    markup: InlineKeyboardMarkup, ids: dict[str, str]
) -> InlineKeyboardMarkup | None:
    """
    A copy of `markup` with known leading emoji turned into icons, or None
    when nothing in it changes. The original is left as it was.
    """
    if not ids:
        return None
    changed = False
    rows: list[list[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard:
        new_row = []
        for button in row:
            split = None if button.icon_custom_emoji_id else split_leading_emoji(button.text)
            icon_id = ids.get(split[0]) if split else None
            if icon_id:
                button = button.model_copy(
                    update={"text": split[1], "icon_custom_emoji_id": icon_id}
                )
                changed = True
            new_row.append(button)
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows) if changed else None


class ButtonIconsMiddleware(BaseRequestMiddleware):
    """
    Puts the set's icons on every inline keyboard the bot sends.

    The set is read lazily, on the first keyboard, so every process that
    sends with this bot -- the poller and the payment webhook alike -- gets
    the icons without a startup hook of its own.
    """

    def __init__(self, set_name: str):
        self.set_name = set_name.strip()
        self.ids: dict[str, str] = {}
        self.disabled = not self.set_name
        self._loaded_at = 0.0
        self._loaded = False
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self, bot) -> None:
        if self._loaded:
            return
        if self._loaded_at and time.monotonic() - self._loaded_at < RETRY_SECONDS:
            return
        async with self._lock:
            if self._loaded:
                return
            self._loaded_at = time.monotonic()
            try:
                sticker_set = await bot.get_sticker_set(name=self.set_name)
            except Exception as exc:
                logger.warning("Button icons: could not read set %r: %s", self.set_name, exc)
                return
            ids = {}
            for sticker in sticker_set.stickers:
                if sticker.custom_emoji_id and sticker.emoji:
                    ids.setdefault(normalize(sticker.emoji), sticker.custom_emoji_id)
            missing = [e for e, _ in ICONS if normalize(e) not in ids]
            if missing:
                logger.info("Button icons: set %r has no icon for %s", self.set_name, " ".join(missing))
            self.ids = ids
            self._loaded = True
            logger.info("Button icons: %d icons from %r", len(ids), self.set_name)

    async def __call__(self, make_request, bot, method):
        markup = getattr(method, "reply_markup", None)
        if self.disabled or not isinstance(markup, InlineKeyboardMarkup):
            return await make_request(bot, method)

        await self._ensure_loaded(bot)
        iconed = apply_icons(markup, self.ids)
        if iconed is None:
            return await make_request(bot, method)

        try:
            return await make_request(bot, method.model_copy(update={"reply_markup": iconed}))
        except TelegramBadRequest as exc:
            # Sent again as written. Only when that goes through were the
            # icons to blame -- an error that repeats without them (say,
            # "message is not modified") is the caller's and is raised as is.
            result = await make_request(bot, method)
            self.disabled = True
            logger.error(
                "Button icons switched off until restart: Telegram refused them (%s). "
                "Is the bot owner's Telegram Premium active?",
                exc,
            )
            return result

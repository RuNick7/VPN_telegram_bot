"""
Create the custom emoji set behind the bot's button icons.

    python user_bot/make_emoji_pack.py                 # owner: the first ADMIN_IDS entry
    python user_bot/make_emoji_pack.py --owner 123456789 --name kaira_icons
    python user_bot/make_emoji_pack.py --images ~/my-pack --name kaira_icons_v2

Run once, where USER_BOT_TOKEN is set -- in the bot's container:

    docker compose exec bots python user_bot/make_emoji_pack.py

It uploads the 31 icons from user_bot/data/button_icons (or `--images`, the
same file names), each tagged with the ordinary emoji of the buttons it
replaces, as an adaptive set -- the icons take the colour of the text around
them, white on a coloured button. The set belongs to `--owner`, who then
manages it in @Stickers like any of their own. Last, it prints the line to put
in .env:

    BUTTON_ICONS_SET=kaira_icons_by_<bot>

A pack drawn later goes the same way: same file names under `--images`, a
new `--name`, the new value in .env, restart.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from tgvpn_shared.settings import get_settings

from button_icons import ICON_DIR, ICONS

# Telegram's rule for set names, before the `_by_<bot>` suffix is added.
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")


def plan(images: Path) -> list[tuple[str, Path]]:
    """
    (emoji, file) for every icon, in order, or SystemExit naming what is wrong.

    Checked before anything is sent: a set created with a hole in it would
    have to be deleted and made again.
    """
    problems = []
    entries = []
    for emoji, name in ICONS:
        path = images / f"{name}.png"
        if not path.is_file():
            problems.append(f"нет файла {path}")
            continue
        head = path.read_bytes()[:24]
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            problems.append(f"{path} — не PNG")
            continue
        width, height = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if (width, height) != (100, 100):
            problems.append(f"{path} — {width}×{height}, нужно 100×100")
            continue
        entries.append((emoji, path))
    if problems:
        raise SystemExit("Иконки не готовы:\n  " + "\n  ".join(problems))
    return entries


def set_name(name: str, bot_username: str) -> str:
    if not NAME_RE.fullmatch(name) or "__" in name:
        raise SystemExit(
            f"Имя {name!r} не подходит: латиница, цифры и одиночные подчёркивания, "
            "начинается с буквы."
        )
    return f"{name}_by_{bot_username}"


async def create(owner: int, name: str, title: str, images: Path) -> str:
    from aiogram import Bot
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.types import BufferedInputFile, InputSticker

    entries = plan(images)
    settings = get_settings()
    settings.require("user_bot_token")
    bot = Bot(token=settings.user_bot_token)
    try:
        me = await bot.get_me()
        full_name = set_name(name, me.username)

        try:
            await bot.get_sticker_set(name=full_name)
        except TelegramBadRequest:
            pass  # does not exist yet -- the expected case
        else:
            raise SystemExit(
                f"Набор {full_name} уже есть: https://t.me/addemoji/{full_name}\n"
                "Возьмите другое --name или удалите набор в @Stickers (/delpack)."
            )

        stickers = [
            InputSticker(
                sticker=BufferedInputFile(path.read_bytes(), filename=path.name),
                format="static",
                emoji_list=[emoji],
            )
            for emoji, path in entries
        ]
        await bot.create_new_sticker_set(
            user_id=owner,
            name=full_name,
            title=title,
            stickers=stickers,
            sticker_type="custom_emoji",
            needs_repainting=True,
        )
        created = await bot.get_sticker_set(name=full_name)
        print(f"Готово: {len(created.stickers)} иконок — https://t.me/addemoji/{full_name}")
        print("Добавьте в .env и перезапустите бота:")
        print(f"BUTTON_ICONS_SET={full_name}")
        return full_name
    finally:
        await bot.session.close()


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Создать набор эмодзи для иконок кнопок бота.")
    parser.add_argument(
        "--owner",
        type=int,
        default=settings.primary_admin_id,
        help="Telegram ID владельца набора (по умолчанию первый из ADMIN_IDS). "
        "Он должен хотя бы раз написать боту.",
    )
    parser.add_argument("--name", default="kaira_icons", help="Имя набора без _by_<бот>.")
    parser.add_argument("--title", default="KairaVPN icons", help="Название набора.")
    parser.add_argument(
        "--images", type=Path, default=ICON_DIR, help="Папка с PNG 100×100 (имена как в ICONS)."
    )
    parser.add_argument(
        "--check", action="store_true", help="Только проверить картинки, ничего не отправлять."
    )
    args = parser.parse_args(argv)

    entries = plan(args.images.expanduser())
    if args.check:
        print(f"Иконки в порядке: {len(entries)} шт. из {args.images}")
        return
    if not args.owner:
        raise SystemExit("Укажите --owner: ADMIN_IDS пуст.")
    asyncio.run(create(args.owner, args.name, args.title, args.images.expanduser()))


if __name__ == "__main__":
    main(sys.argv[1:])

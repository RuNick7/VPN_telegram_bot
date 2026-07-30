"""
Per-platform VPN setup instructions.

Every platform used to have its own handler pair (`os:<platform>` and
`manual_setup:<platform>`) that differed only in copy -- 14 handlers repeating
the same fetch-url / build-caption / send-with-video sequence. They are now one
table of `PlatformSpec`s plus two generic handlers.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile
from tgvpn_shared.remnawave import UserNotFoundError
from tgvpn_shared.settings import get_settings

from app.services.remnawave.vpn_service import get_client, get_subscription_url
from handlers.keyboards import (
    manual_setup_keyboard,
    pay_keyboard,
    support_faq_back_to_devices_keyboard,
)
from precache_videos import VIDEOS

router = Router()

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "data" / "video" / "cache.json"

# Ceiling on the panel round-trip behind a device button, so a slow Remnawave
# shows a retry prompt instead of an unresponsive button.
SUBSCRIPTION_URL_TIMEOUT_SECONDS = 10.0

# Wraps a deep link so it opens reliably from inside Telegram's in-app browser.
_AUTO_IMPORT_WRAPPER = "https://vless-outline.ru/auto/?url="


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


VIDEO_ID_CACHE: dict = _load_cache()


# -- instruction text builders ---------------------------------------------


def _manual_link_block(title: str, subscription_url: str) -> str:
    return (
        f"<b>Настройка VPN на {title}</b>\n\n"
        "Ручная установка\n"
        "---------------------------------------------\n"
        f"<code>{escape(subscription_url, quote=True)}</code>\n"
        "---------------------------------------------\n\n"
    )


def _auto_import_link(subscription_url: str, scheme: str = "happ://add/") -> str:
    """Telegram-safe deep link that imports the profile in one tap."""
    return escape(
        _AUTO_IMPORT_WRAPPER + quote(f"{scheme}{subscription_url}", safe=":/?=&"),
        quote=True,
    )


def _happ_instruction(title: str, install_html: str) -> Callable[[str], str]:
    """
    The shared Happ flow: install, tap to auto-import, press connect.

    Four platforms (Android/iOS/Windows/macOS) differ only in where the app is
    downloaded from, so that is the only thing each one supplies.
    """

    def build(subscription_url: str) -> str:
        return (
            _manual_link_block(title, subscription_url)
            + f"<b>Шаг 1.</b> {install_html}\n\n"
            "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
            f'<a href="{_auto_import_link(subscription_url)}">Нажмите для подключения</a>\n\n'
            "<b>Шаг 3.</b> После импорта откройте приложение и нажмите на кнопку включения.\n\n"
        )

    return build


def _clipboard_manual(subscription_url: str) -> str:
    """The 'couldn't connect' fallback for every Happ platform."""
    return (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{escape(subscription_url, quote=True)}</code>\n\n"
        "2️⃣ Откройте Happ\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите на кнопку включения.\n\n"
    )


_APP_STORE_HTML = (
    '<a href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215">Happ</a> из App Store.\n'
    'Для региона RU: <a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">Happ (RU)</a>'
)

_LINUX_INSTRUCTION = (
    "<b>Настройка VPN на Linux (NekoRay)</b>\n\n"
    "<b>Шаг 1.</b> Скачайте NekoRay с GitHub:\n"
    '<a href="https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-linux64.zip">'
    "ZIP для Linux</a>\n"
    '<a href="https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb">'
    "DEB для Debian/Ubuntu</a>\n\n"
    "<b>Шаг 2.</b> Распакуйте архив в выбранную директорию (или установите DEB).\n\n"
    "<b>Шаг 3.</b> Перейдите в папку nekoray и запустите launcher или nekobox "
    "(или запустите из меню приложений, если установили DEB).\n\n"
    "<b>Шаг 4.</b> Скопируйте вашу ссылку на подписку:\n\n"
    "<code>{url}</code>\n\n"
    "<b>Шаг 5.</b> Выберите Сервер → Добавить профиль из буфера обмена.\n\n"
    "<b>Шаг 6.</b> Выберите «Как подписку (создать новую группу)».\n\n"
    "<b>Шаг 7.</b> Откройте появившуюся вкладку.\n\n"
    "<b>Шаг 8.</b> Включите «Режим TUN» вверху экрана. При необходимости перезапустите приложение, "
    "если Nekobox попросит об этом. Это пропустит весь интернет-трафик через VPN. "
    "Чтобы оставить VPN только для браузера (без расширений), выберите «Системный прокси».\n\n"
    "<b>Шаг 9.</b> Нажмите «URL‑Тест» — это проверит доступные конфигурации.\n\n"
    "<b>Шаг 10.</b> Нажмите правой кнопкой мыши по конфигурации → «Запустить». "
    "Чтобы выключить VPN, выберите «Остановить».\n\n"
    "<b>Шаг 11.</b> Для обновления подписок: Сервер → Текущая группа → Обновить подписки.\n\n"
)

_TV_PAIRING_STEPS = (
    "<b>Шаг 2.</b> Установите Happ на телефон (Google Play / App Store) и "
    "подключите VPN по инструкции из раздела Android/iOS.\n\n"
    "<b>Шаг 3.</b> Отсканируйте QR‑код с телефона и выберите отправку нужных конфигураций.\n\n"
    "<b>Шаг 4.</b> Выберите конфигурацию на телевизоре и нажмите на кнопку включения.\n\n"
)


# -- the table -------------------------------------------------------------


@dataclass(frozen=True)
class PlatformSpec:
    """Everything that differs between one platform's instructions and another's."""

    # Builds the main `os:<key>` message. Takes the subscription URL, which is
    # an empty string for platforms that don't need one.
    instruction: Callable[[str], str]
    # Builds the `manual_setup:<key>` follow-up.
    manual: Callable[[str], str]
    # Whether either message embeds the user's subscription URL. Platforms
    # without one (TVs, paired from a phone) skip the panel round-trip.
    needs_url: bool = True
    # Alias into precache_videos.VIDEOS; None means text-only instructions.
    video_alias: str | None = None
    # Whether the manual follow-up needs the subscription URL specifically.
    manual_needs_url: bool = field(default=True)
    # Edit the message in place instead of sending a new one.
    manual_edits_message: bool = False
    # Remove the instruction message after sending the manual fallback.
    manual_deletes_origin: bool = False


PLATFORMS: dict[str, PlatformSpec] = {
    "android": PlatformSpec(
        instruction=_happ_instruction(
            "Android",
            '<a href="https://play.google.com/store/apps/details?id=com.happproxy&hl=ru&pli=1">'
            "Установите приложение Happ</a> из Google Play.",
        ),
        manual=_clipboard_manual,
        video_alias="android",
        manual_deletes_origin=True,
    ),
    "ios": PlatformSpec(
        instruction=_happ_instruction("iPhone", f"Установите приложение {_APP_STORE_HTML}"),
        manual=_clipboard_manual,
        video_alias="ios",
    ),
    "windows": PlatformSpec(
        instruction=_happ_instruction(
            "Windows",
            "Скачайте "
            '<a href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe">'
            "Happ</a> для Windows.",
        ),
        manual=_clipboard_manual,
        video_alias="windows",
    ),
    "macos": PlatformSpec(
        instruction=_happ_instruction("macOS", f"Установите {_APP_STORE_HTML}"),
        manual=_clipboard_manual,
        video_alias="macos",
    ),
    "linux": PlatformSpec(
        instruction=lambda url: _LINUX_INSTRUCTION.format(url=escape(url, quote=True)),
        manual=lambda _url: (
            "<b>Не получилось подключиться?</b>\n\n"
            "Если возникли проблемы, напишите в техподдержку или прочитайте ответы на "
            "частые вопросы по кнопкам ниже.\n\n"
        ),
        manual_needs_url=False,
        manual_edits_message=True,
    ),
    "tv": PlatformSpec(
        instruction=lambda _url: (
            "<b>Настройка VPN на Android-TV</b>\n\n"
            "<b>Шаг 1.</b> Установите Happ на Android TV:\n"
            '<a href="https://play.google.com/store/apps/details?id=com.happproxy">Google Play</a> или '
            '<a href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk">'
            "APK‑файл</a>.\n\n"
            "Если устанавливаете через APK, скачайте файл на флешку, "
            "вставьте флешку в телевизор и откройте APK через файловый менеджер на ТВ.\n\n"
            + _TV_PAIRING_STEPS
        ),
        manual=lambda _url: (
            "<b>Если не получилось подключиться</b>\n\n"
            "<b>Шаг 1.</b> Установите Happ из "
            '<a href="https://play.google.com/store/apps/details?id=com.happproxy">Google Play</a> '
            "или скачайте APK: "
            '<a href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk">'
            "Happ.apk</a>\n\n"
            "<b>Шаг 2.</b> Скачайте QR‑код на флешку.\n\n"
            "<b>Шаг 3.</b> На телевизоре откройте Happ → нажмите <i>+</i> → "
            "выберите добавление через QR‑code → укажите файл на флешке.\n\n"
        ),
        needs_url=False,
        manual_needs_url=False,
    ),
    "appletv": PlatformSpec(
        instruction=lambda _url: (
            "<b>Настройка VPN на Apple TV</b>\n\n"
            "<b>Шаг 1.</b> Установите Happ на Apple TV:\n"
            '<a href="https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274">'
            "Happ для Apple TV</a>\n\n" + _TV_PAIRING_STEPS
        ),
        manual=lambda _url: (
            "<b>Не получилось подключиться?</b>\n\n"
            "На экране импорта выберите «Web Import».\n\n"
            "Выберите один из вариантов:\n\n"
            "Откройте в любом браузере сайт tv.happ.su, введите временный код с экрана TV, "
            "затем добавьте данные и нажмите «Отправить».\n\n"
        ),
        needs_url=False,
        manual_needs_url=False,
        manual_edits_message=True,
    ),
}


# -- sending ---------------------------------------------------------------


async def _answer_video_with_cache_fallback(
    cb: CallbackQuery,
    *,
    alias: str,
    caption: str,
    reply_markup,
) -> None:
    """
    Send an instruction video, reusing Telegram's file_id when we have one.

    A cached file_id can go stale (Telegram drops the file); on that specific
    error, fall back to re-uploading the local file and refresh the cache.
    """
    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)

    cached_id = VIDEO_ID_CACHE.get(alias)
    if cached_id:
        try:
            await cb.message.answer_video(
                video=cached_id,
                caption=caption,
                parse_mode="HTML",
                supports_streaming=True,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest as exc:
            if "wrong file identifier" not in str(exc).lower():
                raise
            logging.warning("Invalid cached file_id for alias=%s, falling back to local file", alias)
            VIDEO_ID_CACHE.pop(alias, None)
            _save_cache(VIDEO_ID_CACHE)

    video_path = VIDEOS[alias]
    logging.info("📼 %s video from file: %s exists=%s", alias, video_path, video_path.exists())
    sent = await cb.message.answer_video(
        video=FSInputFile(str(video_path)),
        caption=caption,
        parse_mode="HTML",
        supports_streaming=True,
        reply_markup=reply_markup,
    )
    VIDEO_ID_CACHE[alias] = sent.video.file_id
    _save_cache(VIDEO_ID_CACHE)


async def _resolve_subscription_url(cb: CallbackQuery) -> str | None:
    """
    Fetch the caller's subscription URL, or explain why we can't.

    The link is handed out regardless of subscription state -- an expired
    subscription means fewer servers behind the same link, not no link. Only a
    panel account that no longer exists (deleted by the inactive-user cleanup)
    leaves nothing to give, and that is the one case that prompts for payment.

    Returns None after having already replied to the user.
    """
    try:
        return await asyncio.wait_for(
            get_subscription_url(cb.from_user.id),
            timeout=SUBSCRIPTION_URL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await cb.answer("⏱ Сервер не отвечает, попробуйте через минуту.", show_alert=True)
        return None
    except UserNotFoundError:
        await cb.answer()
        await cb.message.answer(
            "🚫 Профиль не найден на сервере.\n\n"
            "Оформите подписку, чтобы получить доступ:",
            parse_mode="HTML",
            reply_markup=pay_keyboard(),
        )
        return None
    except Exception:
        # The cached panel token may have gone stale -- drop it so the user's
        # next attempt authenticates freshly.
        get_client().invalidate_token()
        raise


@router.callback_query(F.data.startswith("os:"))
async def platform_instruction(cb: CallbackQuery) -> None:
    """Send setup instructions for the chosen platform."""
    key = cb.data.split(":", 1)[1]
    spec = PLATFORMS.get(key)
    if spec is None:
        await cb.answer()
        return

    subscription_url = ""
    if spec.needs_url:
        subscription_url = await _resolve_subscription_url(cb)
        if not subscription_url:
            return

    text = spec.instruction(subscription_url)
    keyboard = manual_setup_keyboard(key)
    await cb.answer()

    if spec.video_alias and get_settings().show_video_instructions:
        await _answer_video_with_cache_fallback(
            cb, alias=spec.video_alias, caption=text, reply_markup=keyboard
        )
        return

    await cb.message.answer(
        text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("manual_setup:"))
async def platform_manual_setup(cb: CallbackQuery) -> None:
    """Send the 'couldn't connect' fallback for the chosen platform."""
    spec = PLATFORMS.get(cb.data.split(":", 1)[1])
    if spec is None:
        await cb.answer()
        return

    subscription_url = ""
    if spec.manual_needs_url:
        subscription_url = await _resolve_subscription_url(cb)
        if not subscription_url:
            return

    text = spec.manual(subscription_url)
    keyboard = support_faq_back_to_devices_keyboard()

    if spec.manual_edits_message:
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True
        )
        await cb.answer()
        return

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()
    await cb.message.answer(
        text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True
    )

    if spec.manual_deletes_origin:
        try:
            await cb.message.delete()
        except Exception:
            pass

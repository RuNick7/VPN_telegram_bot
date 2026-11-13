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
    region_help_keyboard,
    support_faq_back_to_devices_keyboard,
)
from precache_videos import VIDEOS

logger = logging.getLogger(__name__)

router = Router()

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "data" / "video" / "cache.json"

# Ceiling on the panel round-trip behind a device button, so a slow Remnawave
# shows a retry prompt instead of an unresponsive button.
SUBSCRIPTION_URL_TIMEOUT_SECONDS = 10.0

def _auto_import_wrapper() -> str:
    """
    Our own redirect for app deep links, or an empty string if we have none.

    Telegram does not render `incy://…` as a link, so the one-tap import step
    has to be an https:// URL that becomes one. That used to be somebody else's
    server, which meant every customer's subscription URL -- the credential,
    whole and sufficient to configure their VPN as them -- went through a third
    party on the way to their own phone.

    Read from WEB_BASE_URL rather than hard-coded, because it is the same site
    and there is no second answer to keep in step. With it unset there is
    nowhere of ours to point at, and the bare deep link is the honest fallback:
    it works everywhere except inside Telegram's own browser, which is exactly
    where it did not work before either.
    """
    base = get_settings().web_base_url.strip().rstrip("/")
    return f"{base}/auto?url=" if base else ""


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            # Starting empty is the right recovery -- the cache is derived data
            # and rebuilds itself. Silence was not: a file that fails to parse
            # every single time looks exactly like a cache that never helps,
            # and nothing said which of the two was happening.
            logger.warning("Setup cache at %s is unreadable, starting empty: %s",
                           CACHE_FILE, exc)
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


VIDEO_ID_CACHE: dict = _load_cache()


# -- instruction text builders ---------------------------------------------

# One app everywhere: Incy takes the full Xray JSON the panel serves, balancers
# included, on phones, desktops and TVs alike. Happ is gone from the bot.
INCY_SCHEME = "incy://import/"

# The real Incy is published by LLC ITDEV. It is missing from the Russian App
# Store, and that store carries look-alikes under the same name from other
# sellers -- which is why the publisher is named wherever the link is.
INCY_APPLE = "https://apps.apple.com/us/app/incy/id6756943388"
INCY_ANDROID = "https://play.google.com/store/apps/details?id=llc.itdev.incy"
# The project keeps a release under the fixed tag `latest` and re-uploads its
# files there on every build. Not /releases/latest/download/: the newest
# release in that repository is often an Android-only one, and a desktop file
# name would 404 there.
INCY_RELEASES = "https://github.com/INCY-DEV/incy-platforms/releases/tag/latest"
INCY_DOWNLOAD = "https://github.com/INCY-DEV/incy-platforms/releases/download/latest/"
INCY_APK = INCY_DOWNLOAD + "Incy.apk"
APPLE_ACCOUNT = "https://account.apple.com/"


def _manual_link_block(title: str, subscription_url: str) -> str:
    return (
        f"<b>Настройка VPN на {title}</b>\n\n"
        "Ссылка подписки для ручного добавления:\n"
        "---------------------------------------------\n"
        f"<code>{escape(subscription_url, quote=True)}</code>\n"
        "---------------------------------------------\n\n"
    )


def _auto_import_link(subscription_url: str, scheme: str = INCY_SCHEME) -> str:
    """Telegram-safe deep link that imports the profile in one tap."""
    deep_link = f"{scheme}{subscription_url}"
    wrapper = _auto_import_wrapper()
    if not wrapper:
        return escape(deep_link, quote=True)
    # The deep link becomes a query parameter, so everything with a meaning
    # inside a query has to lose it. `:` and `/` are kept legible because they
    # have none there; `&` used to be kept too, and an `&` in a subscription URL
    # would have cut the parameter in half and handed the app the first piece.
    return escape(wrapper + quote(deep_link, safe=":/"), quote=True)


def import_button_url(subscription_url: str) -> str:
    """
    The URL behind «📲 Добавить в Incy», or "" when there can be no button.

    Telegram refuses a URL button with an app scheme outright, so the button
    exists only when our own https:// redirect does. Unescaped: this goes into
    a keyboard, not into HTML.
    """
    if not subscription_url or not _auto_import_wrapper():
        return ""
    return _auto_import_wrapper() + quote(f"{INCY_SCHEME}{subscription_url}", safe=":/")


def _import_step(subscription_url: str) -> str:
    """The one-tap import, as a button when there is one and a link otherwise."""
    if import_button_url(subscription_url):
        return "Нажмите «📲 Добавить в Incy» под этим сообщением — Incy откроется и добавит подписку."
    return (
        "Нажмите ссылку, чтобы подписка добавилась автоматически: "
        f'<a href="{_auto_import_link(subscription_url)}">Добавить в Incy</a>'
    )


def _incy_instruction(title: str, install_html: str) -> Callable[[str], str]:
    """
    The shared Incy flow: install, tap to import, press connect.

    Phones and desktops differ only in where the app is downloaded from, so
    that is the only thing each one supplies.
    """

    def build(subscription_url: str) -> str:
        return (
            _manual_link_block(title, subscription_url)
            + f"<b>Шаг 1.</b> {install_html}\n\n"
            f"<b>Шаг 2.</b> {_import_step(subscription_url)}\n\n"
            "<b>Шаг 3.</b> Откройте Incy, выберите сервер и нажмите кнопку подключения.\n\n"
        )

    return build


def _clipboard_manual(subscription_url: str) -> str:
    """The 'couldn't connect' fallback for every phone and desktop."""
    return (
        "<b>Ручное добавление подписки</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{escape(subscription_url, quote=True)}</code>\n\n"
        "2️⃣ Откройте Incy\n"
        "3️⃣ Добавьте подписку из буфера обмена → выберите сервер → нажмите кнопку подключения.\n\n"
    )


_ANDROID_INSTALL = (
    f'<a href="{INCY_ANDROID}">Установите Incy</a> из Google Play. '
    f'Если Google Play недоступен — <a href="{INCY_APK}">скачайте APK</a>.'
)

_IOS_INSTALL = (
    f'Установите <a href="{INCY_APPLE}">Incy</a> из App Store — разработчик <b>LLC ITDEV</b>. '
    "Если его не видно в App Store, нажмите «🔍 Не нахожу Incy в App Store»."
)

_WINDOWS_INSTALL = (
    f'Скачайте <a href="{INCY_DOWNLOAD}incy-windows-setup.exe">установщик Incy для Windows</a> '
    "и запустите его. Без установки — "
    f'<a href="{INCY_DOWNLOAD}incy-windows-portable.zip">portable-версия</a>.'
)

# The .dmg rather than the App Store: it needs no change of App Store region,
# and it is the only build for Intel Macs at all.
_MACOS_INSTALL = (
    "Скачайте Incy для своего Mac: "
    f'<a href="{INCY_DOWNLOAD}incy-macos-arm64.dmg">Apple Silicon (M1 и новее)</a> или '
    f'<a href="{INCY_DOWNLOAD}incy-macos-intel.dmg">Intel</a>. '
    "Откройте файл .dmg и перетащите Incy в «Программы»."
)


def _linux_instruction(subscription_url: str) -> str:
    url = escape(subscription_url, quote=True)
    return (
        "<b>Настройка VPN на Linux (Incy)</b>\n\n"
        "<b>Шаг 1.</b> Скачайте Incy под свою систему:\n"
        f'<a href="{INCY_DOWNLOAD}incy-linux-x64.deb">DEB — Debian, Ubuntu, Mint</a>\n'
        f'<a href="{INCY_DOWNLOAD}incy-linux-x64.rpm">RPM — Fedora</a>\n'
        f'<a href="{INCY_DOWNLOAD}incy-linux-x64.pkg.tar.zst">Arch Linux</a>\n'
        f'Для ARM64: <a href="{INCY_DOWNLOAD}incy-linux-arm64.deb">DEB</a> или '
        f'<a href="{INCY_DOWNLOAD}incy-linux-arm64.rpm">RPM</a>. '
        f'Остальные сборки — на <a href="{INCY_RELEASES}">странице релиза</a>.\n\n'
        "<b>Шаг 2.</b> Установите пакет из папки, куда он скачался:\n"
        "<code>sudo apt install ./incy-linux-x64.deb</code>\n"
        "<code>sudo dnf install ./incy-linux-x64.rpm</code>\n"
        "<code>sudo pacman -U incy-linux-x64.pkg.tar.zst</code>\n\n"
        "<b>Шаг 3.</b> Запустите Incy из меню приложений.\n\n"
        f"<b>Шаг 4.</b> {_import_step(subscription_url)}\n"
        "Если не сработало, скопируйте ссылку и добавьте её в Incy из буфера обмена:\n\n"
        f"<code>{url}</code>\n\n"
        "<b>Шаг 5.</b> Выберите сервер и нажмите кнопку подключения.\n\n"
    )


_TV_PAIRING_STEPS = (
    "<b>Шаг 2.</b> Установите Incy на телефон и добавьте подписку по инструкции "
    "для Android или iPhone.\n\n"
    "<b>Шаг 3.</b> Откройте Incy на телевизоре и перейдите к добавлению подписки — "
    "на экране появятся код из 8 символов и QR‑код.\n\n"
    "<b>Шаг 4.</b> В Incy на телефоне отсканируйте QR‑код или введите код с экрана — "
    "подписка перейдёт на телевизор.\n\n"
    "<b>Шаг 5.</b> Выберите сервер на телевизоре и нажмите кнопку подключения.\n\n"
)

_TV_MANUAL = (
    "<b>Если не получилось подключиться</b>\n\n"
    "• Код действует 5 минут. Закройте экран добавления подписки на телевизоре "
    "и откройте снова — появится новый.\n"
    "• Проверьте, что на телефоне подписка уже добавлена и VPN подключается.\n"
    "• Удобнее всего, когда телефон и телевизор в одной сети Wi‑Fi, но передача "
    "работает и через интернет.\n\n"
)

# How to get Incy when the App Store does not show it. The gentler way first:
# a separate Apple ID touches nothing but the App Store, while changing the
# country of the main one has preconditions Apple enforces.
REGION_HELP_HTML = (
    "<b>🔍 Не нахожу Incy в App Store</b>\n\n"
    "В российском App Store Incy нет, а приложения с похожим названием — подделки. "
    "Настоящий Incy выпускает <b>LLC ITDEV</b>. Чтобы его скачать, нужен Apple ID "
    "другой страны, например США.\n\n"
    "<b>Способ 1 — отдельный Apple ID (проще)</b>\n"
    f'1. Создайте новый Apple ID на <a href="{APPLE_ACCOUNT}">account.apple.com</a>, '
    "страна — США.\n"
    "2. В App Store нажмите на аватар → «Выйти» и войдите с новым Apple ID. "
    "Только в App Store — в настройках iCloud ничего не меняйте.\n"
    "Фото, контакты и iCloud остаются на основном аккаунте.\n\n"
    "<b>Способ 2 — сменить страну основного Apple ID</b>\n"
    "1. Отмените активные подписки и потратьте остаток на балансе Apple ID — "
    "иначе Apple не даст сменить страну.\n"
    "2. Настройки → ваше имя → «Медиаматериалы и покупки» → «Просмотреть» → "
    "«Страна или регион» → «Изменить страну или регион».\n"
    "3. Выберите США, примите условия, способ оплаты — «Нет», адрес — любой адрес в США.\n\n"
    f'<b>Затем</b> откройте <a href="{INCY_APPLE}">Incy в App Store</a> (разработчик LLC ITDEV) '
    "и установите. После этого можно вернуться к прежнему Apple ID — Incy останется "
    "и будет работать, а обновлять его нужно будет из того аккаунта, с которого он установлен."
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
    # Every platform is text-only for now: the recorded videos show Happ, and
    # the code stays for when videos of Incy exist.
    video_alias: str | None = None
    # Whether the manual follow-up needs the subscription URL specifically.
    manual_needs_url: bool = field(default=True)
    # Edit the message in place instead of sending a new one.
    manual_edits_message: bool = False
    # Remove the instruction message after sending the manual fallback.
    manual_deletes_origin: bool = False
    # Offer «🔍 Не нахожу Incy в App Store» -- the Apple devices that install
    # from the App Store, where a Russian Apple ID cannot see the app.
    region_help: bool = False


PLATFORMS: dict[str, PlatformSpec] = {
    "android": PlatformSpec(
        instruction=_incy_instruction("Android", _ANDROID_INSTALL),
        manual=_clipboard_manual,
        manual_deletes_origin=True,
    ),
    "ios": PlatformSpec(
        instruction=_incy_instruction("iPhone", _IOS_INSTALL),
        manual=_clipboard_manual,
        region_help=True,
    ),
    "windows": PlatformSpec(
        instruction=_incy_instruction("Windows", _WINDOWS_INSTALL),
        manual=_clipboard_manual,
    ),
    "macos": PlatformSpec(
        instruction=_incy_instruction("macOS", _MACOS_INSTALL),
        manual=_clipboard_manual,
    ),
    "linux": PlatformSpec(
        instruction=_linux_instruction,
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
            "<b>Настройка VPN на Android TV</b>\n\n"
            "<b>Шаг 1.</b> Установите Incy на телевизор: "
            f'<a href="{INCY_ANDROID}">Google Play</a> или '
            f'<a href="{INCY_APK}">APK‑файл</a>.\n'
            "Если устанавливаете через APK, скачайте файл на флешку, "
            "вставьте флешку в телевизор и откройте APK через файловый менеджер на ТВ.\n\n"
            + _TV_PAIRING_STEPS
        ),
        manual=lambda _url: _TV_MANUAL,
        needs_url=False,
        manual_needs_url=False,
    ),
    "appletv": PlatformSpec(
        instruction=lambda _url: (
            "<b>Настройка VPN на Apple TV</b>\n\n"
            f'<b>Шаг 1.</b> Установите <a href="{INCY_APPLE}">Incy</a> из App Store '
            "на телевизоре (разработчик LLC ITDEV, нужен tvOS 17 или новее). "
            "Если его не видно в App Store, нажмите «🔍 Не нахожу Incy в App Store».\n\n"
            + _TV_PAIRING_STEPS
        ),
        manual=lambda _url: _TV_MANUAL,
        needs_url=False,
        manual_needs_url=False,
        region_help=True,
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
    keyboard = manual_setup_keyboard(
        key,
        import_url=import_button_url(subscription_url),
        region_help=spec.region_help,
    )
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


@router.callback_query(F.data.startswith("region_help:"))
async def platform_region_help(cb: CallbackQuery) -> None:
    """«🔍 Не нахожу Incy в App Store»: how to reach the real app."""
    key = cb.data.split(":", 1)[1]
    if key not in PLATFORMS:
        await cb.answer()
        return
    await cb.answer()
    await cb.message.answer(
        REGION_HELP_HTML,
        parse_mode="HTML",
        reply_markup=region_help_keyboard(key),
        disable_web_page_preview=True,
    )

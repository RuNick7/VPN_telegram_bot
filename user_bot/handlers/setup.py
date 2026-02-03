import json
import logging
from pathlib import Path
from urllib.parse import quote
from html import escape

from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.types import CallbackQuery, FSInputFile

from app.services.remnawave.vpn_service import get_token, get_subscription_url
from handlers.keyboards import (
    back_to_devices_keyboard,
    manual_setup_keyboard,
    support_faq_back_to_devices_keyboard,
)
from precache_videos import VIDEOS


router = Router()


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "video"
CACHE_FILE = DATA_DIR / "cache.json"

ANDROID_ALIAS = "android"
IOS_ALIAS = "ios"
WIN_ALIAS = "windows"
MAC_ALIAS = "macos"


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

def _manual_link_block(title: str, subscription_url: str) -> str:
    url = escape(subscription_url, quote=True)
    return (
        f"<b>Настройка VPN на {title}</b>\n\n"
        "Ручная установка\n"
        "---------------------------------------------\n"
        f"<code>{url}</code>\n"
        "---------------------------------------------\n\n"
    )


@router.callback_query(F.data == "os:android")
async def android_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)
    auto_url = (
        "https://vless-outline.ru/auto/?url="
        f"v2RayTun://import/{subscription_url}"
    )
    play_url = escape(
        "https://play.google.com/store/apps/details?id=com.v2raytun.android&hl=ru",
        quote=True,
    )
    caption = (
        _manual_link_block("Android", subscription_url)
        +
        "<b>Шаг 1.</b> Установите приложение "
        f"<a href=\"{play_url}\">V2Ray / Tun</a> из Google Play.\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите <i>Start</i>.\n\n"
    )

    reply_kb = manual_setup_keyboard("android")

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)
    await cb.answer()

    if ANDROID_ALIAS in VIDEO_ID_CACHE:
        video_src = VIDEO_ID_CACHE[ANDROID_ALIAS]
    else:
        video_path = VIDEOS[ANDROID_ALIAS]
        video_src = FSInputFile(str(video_path))

        logging.info(
            "📼 android send from file: %s  exists=%s",
            video_path,
            video_path.exists(),
        )

    sent_msg = await cb.message.answer_video(
        video=video_src,
        caption=caption,
        parse_mode="HTML",
        supports_streaming=True,
        reply_markup=reply_kb,
    )

    if ANDROID_ALIAS not in VIDEO_ID_CACHE:
        VIDEO_ID_CACHE[ANDROID_ALIAS] = sent_msg.video.file_id
        _save_cache(VIDEO_ID_CACHE)

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "os:ios")
async def ios_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)

    auto_url = (
        "https://vless-outline.ru/auto/?url="
        f"v2RayTun://import/{subscription_url}"
    )
    play_url = escape(
        "https://apps.apple.com/ru/app/v2raytun/id6476628951",
        quote=True,
    )

    caption = (
        _manual_link_block("iPhone", subscription_url)
        +
        "<b>Шаг 1.</b> Установите приложение "
        f"<a href=\"{play_url}\">V2Ray / Tun</a> из App Store.\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите <i>Start</i>.\n\n"
    )

    kb = manual_setup_keyboard("ios")

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)
    await cb.answer()

    if IOS_ALIAS in VIDEO_ID_CACHE:
        video_src = VIDEO_ID_CACHE[IOS_ALIAS]
    else:
        video_path = VIDEOS[IOS_ALIAS]
        logging.info("📼 ios video from file: %s  exists=%s",
                     video_path, video_path.exists())
        video_src = FSInputFile(str(video_path))

    sent_msg = await cb.message.answer_video(
        video=video_src,
        caption=caption,
        parse_mode="HTML",
        supports_streaming=True,
        reply_markup=kb,
    )

    if IOS_ALIAS not in VIDEO_ID_CACHE:
        VIDEO_ID_CACHE[IOS_ALIAS] = sent_msg.video.file_id
        _save_cache(VIDEO_ID_CACHE)

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "os:windows")
async def windows_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)

    hiddify_raw = f"hiddify://import/{subscription_url}"
    hiddify_wrap = (
        "https://vless-outline.ru/auto/?url="
        f"{quote(hiddify_raw, safe=':/?=&')}"
    )

    play_url = (
        "https://github.com/hiddify/hiddify-app/releases/download/"
        "v2.5.7/Hiddify-Windows-Setup-x64.exe"
    )

    caption = (
        _manual_link_block("Windows", subscription_url)
        +
        f"<b>Шаг 1.</b> Скачайте <a href=\"{escape(play_url, quote=True)}\">"
        "Hiddify</a> для Windows.\n\n"
        "<b>Шаг 2.</b> Нажмите, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(hiddify_wrap, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта нажмите <i>Start</i>.\n\n"
    )

    kb = manual_setup_keyboard("windows")

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)
    await cb.answer()

    if WIN_ALIAS in VIDEO_ID_CACHE:
        video_src = VIDEO_ID_CACHE[WIN_ALIAS]
    else:
        video_path = VIDEOS[WIN_ALIAS]
        logging.info("📼 windows video: %s  exists=%s",
                     video_path, video_path.exists())
        video_src = FSInputFile(str(video_path))

    sent_msg = await cb.message.answer_video(
        video=video_src,
        caption=caption,
        parse_mode="HTML",
        supports_streaming=True,
        reply_markup=kb,
    )

    if WIN_ALIAS not in VIDEO_ID_CACHE:
        VIDEO_ID_CACHE[WIN_ALIAS] = sent_msg.video.file_id
        _save_cache(VIDEO_ID_CACHE)

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "os:linux")
async def linux_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)

    hiddify_raw = f"hiddify://import/{subscription_url}"
    hiddify_wrap = (
        "https://vless-outline.ru/auto/?url="
        f"{quote(hiddify_raw, safe=':/?=&')}"
    )

    play_url = (
        "https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7"
    )

    text = (
        "<b>Настройка VPN на Linux</b>\n\n"
        f"<b>Шаг 1.</b> Скачайте <a href=\"{escape(play_url, quote=True)}\">Hiddify</a>\n\n"
        "<b>Шаг 2.</b> Нажмите, чтобы профиль импортировался автоматически:"
        f"<a href=\"{escape(hiddify_wrap, quote=True)}\"> Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта нажмите на кнопку <i>Start</i>.\n\n"
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manual_setup_keyboard("linux"),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "os:tv")
async def tv_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)

    text = (
        "<b>Настройка VPN на Android-TV</b>\n\n"
        "<b>Шаг 1.</b> Установите на телевизор приложение v2raytun из Google Play.\n\n"
        "<b>Шаг 2.</b> Откройте приложение → <i>Import</i> / <i>Link</i> "
        "и вставьте эту ссылку конфигурации:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "<b>Шаг 3.</b> Сохраните → выберите любой сервер → нажмите <i>Connect</i>."
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "os:macos")
async def macos_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id
    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)

    auto_url = (
        "https://vless-outline.ru/auto/?url="
        f"v2raytun://import/{subscription_url}"
    )

    play_url = escape(
        "https://apps.apple.com/ru/app/v2raytun/id6476628951",
        quote=True,
    )

    caption = (
        _manual_link_block("macOS", subscription_url)
        +
        "<b>Шаг 1.</b> Установите "
        f"<a href=\"{play_url}\">V2Ray/Tun</a> из App Store.\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите <i>Start</i>.\n\n"
    )

    kb = manual_setup_keyboard("macos")

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)
    await cb.answer()

    if MAC_ALIAS in VIDEO_ID_CACHE:
        video_src = VIDEO_ID_CACHE[MAC_ALIAS]
    else:
        video_path = VIDEOS[MAC_ALIAS]
        logging.info("📼 macOS video: %s  exists=%s", video_path, video_path.exists())
        video_src = FSInputFile(str(video_path))

    sent_msg = await cb.message.answer_video(
        video=video_src,
        caption=caption,
        parse_mode="HTML",
        supports_streaming=True,
        reply_markup=kb,
    )

    if MAC_ALIAS not in VIDEO_ID_CACHE:
        VIDEO_ID_CACHE[MAC_ALIAS] = sent_msg.video.file_id
        _save_cache(VIDEO_ID_CACHE)

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "manual_setup:ios")
async def manual_setup_ios(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте V2Ray/Tun\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите <b>Connect</b>.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "manual_setup:android")
async def manual_setup_android(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте V2Ray/Tun\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите <b>Connect</b>.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "manual_setup:windows")
async def manual_setup_windows(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте Hiddify\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Добавьте из буфера обмена → выберите сервер → нажмите <b>Connect</b>.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "manual_setup:linux")
async def manual_setup_linux(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте Hiddify\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Добавить из буфера обмена → выберите сервер → нажмите <b>Connect</b>.\n\n"
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "manual_setup:macos")
async def manual_setup_macos(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте V2Ray/Tun\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите <b>Connect</b>.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )

import json
import logging
import os
from pathlib import Path
from urllib.parse import quote
from html import escape
from io import BytesIO

from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.types.input_file import BufferedInputFile
import qrcode

from app.services.remnawave.vpn_service import get_token, get_subscription_url
from handlers.keyboards import (
    back_to_devices_keyboard,
    manual_setup_keyboard,
    support_faq_back_to_devices_keyboard,
)
from precache_videos import VIDEOS


router = Router()
def _make_qr_png(data: str, filename: str = "subscription_qr.png") -> BufferedInputFile:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return BufferedInputFile(buf.read(), filename=filename)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "video"
CACHE_FILE = DATA_DIR / "cache.json"

ANDROID_ALIAS = "android"
IOS_ALIAS = "ios"
WIN_ALIAS = "windows"
MAC_ALIAS = "macos"


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SHOW_VIDEO_INSTRUCTIONS = _env_bool("SHOW_VIDEO_INSTRUCTIONS", True)


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


async def _send_instruction_without_video(cb: CallbackQuery, text: str, reply_markup) -> None:
    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "os:android")
async def android_instruction(cb: CallbackQuery) -> None:
    tg_id = cb.from_user.id

    token = get_token(tg_id)
    subscription_url = get_subscription_url(tg_id, token)
    auto_url = (
        "https://vless-outline.ru/auto/?url="
        f"happ://add/{subscription_url}"
    )
    play_url = escape(
        "https://play.google.com/store/apps/details?id=com.happproxy&hl=ru&pli=1",
        quote=True,
    )
    caption = (
        _manual_link_block("Android", subscription_url)
        +
        "<b>Шаг 1.</b> Установите приложение "
        f"<a href=\"{play_url}\">Happ</a> из Google Play.\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите на кнопку включения.\n\n"
    )

    reply_kb = manual_setup_keyboard("android")
    await cb.answer()

    if not SHOW_VIDEO_INSTRUCTIONS:
        await _send_instruction_without_video(cb, caption, reply_kb)
        return

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)

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
        f"happ://add/{subscription_url}"
    )
    play_url = escape(
        "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
        quote=True,
    )
    ru_play_url = escape(
        "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
        quote=True,
    )

    caption = (
        _manual_link_block("iPhone", subscription_url)
        +
        "<b>Шаг 1.</b> Установите приложение "
        f"<a href=\"{play_url}\">Happ</a> из App Store.\n"
        f"Для региона RU: <a href=\"{ru_play_url}\">Happ (RU)</a>\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите на кнопку включения.\n\n"
    )

    kb = manual_setup_keyboard("ios")
    await cb.answer()

    if not SHOW_VIDEO_INSTRUCTIONS:
        await _send_instruction_without_video(cb, caption, kb)
        return

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)

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

    happ_raw = f"happ://add/{subscription_url}"
    happ_wrap = (
        "https://vless-outline.ru/auto/?url="
        f"{quote(happ_raw, safe=':/?=&')}"
    )

    play_url = (
        "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/"
        "setup-Happ.x64.exe"
    )

    caption = (
        _manual_link_block("Windows", subscription_url)
        +
        f"<b>Шаг 1.</b> Скачайте <a href=\"{escape(play_url, quote=True)}\">"
        "Happ</a> для Windows.\n\n"
        "<b>Шаг 2.</b> Нажмите, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(happ_wrap, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта нажмите на кнопку включения.\n\n"
    )

    kb = manual_setup_keyboard("windows")
    await cb.answer()

    if not SHOW_VIDEO_INSTRUCTIONS:
        await _send_instruction_without_video(cb, caption, kb)
        return

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)

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
        "<b>Настройка VPN на Linux (NekoRay)</b>\n\n"
        "<b>Шаг 1.</b> Скачайте NekoRay с GitHub:\n"
        "<a href=\"https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-linux64.zip\">"
        "ZIP для Linux</a>\n"
        "<a href=\"https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb\">"
        "DEB для Debian/Ubuntu</a>\n\n"
        "<b>Шаг 2.</b> Распакуйте архив в выбранную директорию (или установите DEB).\n\n"
        "<b>Шаг 3.</b> Перейдите в папку nekoray и запустите launcher или nekobox "
        "(или запустите из меню приложений, если установили DEB).\n\n"
        "<b>Шаг 4.</b> Скопируйте вашу ссылку на подписку:\n\n"
        f"<code>{subscription_url}</code>\n\n"
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

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manual_setup_keyboard("linux"),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "os:tv")
async def tv_instruction(cb: CallbackQuery) -> None:
    text = (
        "<b>Настройка VPN на Android-TV</b>\n\n"
        "<b>Шаг 1.</b> Установите Happ на Android TV:\n"
        "<a href=\"https://play.google.com/store/apps/details?id=com.happproxy\">"
        "Google Play</a> или "
        "<a href=\"https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk\">"
        "APK‑файл</a>.\n"
        "\n"
        "Если устанавливаете через APK, скачайте файл на флешку, "
        "вставьте флешку в телевизор и откройте APK через файловый менеджер на ТВ.\n\n"
        "<b>Шаг 2.</b> Установите Happ на телефон (Google Play / App Store) и "
        "подключите VPN по инструкции из раздела Android/iOS.\n\n"
        "<b>Шаг 3.</b> Отсканируйте QR‑код с телефона и выберите отправку нужных конфигураций.\n\n"
        "<b>Шаг 4.</b> Выберите конфигурацию на телевизоре и нажмите на кнопку включения.\n\n"
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manual_setup_keyboard("tv"),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "os:appletv")
async def appletv_instruction(cb: CallbackQuery) -> None:
    text = (
        "<b>Настройка VPN на Apple TV</b>\n\n"
        "<b>Шаг 1.</b> Установите Happ на Apple TV:\n"
        "<a href=\"https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274\">"
        "Happ для Apple TV</a>\n\n"
        "<b>Шаг 2.</b> Установите Happ на телефон (Google Play / App Store) и "
        "подключите VPN по инструкции из раздела Android/iOS.\n\n"
        "<b>Шаг 3.</b> Отсканируйте QR‑код с телефона и выберите отправку нужных конфигураций.\n\n"
        "<b>Шаг 4.</b> Выберите конфигурацию на телевизоре и нажмите на кнопку включения.\n\n"
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manual_setup_keyboard("appletv"),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data == "manual_setup:appletv")
async def manual_setup_appletv(cb: CallbackQuery) -> None:
    text = (
        "<b>Не получилось подключиться?</b>\n\n"
        "На экране импорта выберите «Web Import».\n\n"
        "Выберите один из вариантов:\n\n"
        "Откройте в любом браузере сайт tv.happ.su, введите временный код с экрана TV, "
        "затем добавьте данные и нажмите «Отправить».\n\n"
    )

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
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
        f"happ://add/{subscription_url}"
    )

    play_url = escape(
        "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
        quote=True,
    )
    ru_play_url = escape(
        "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
        quote=True,
    )

    caption = (
        _manual_link_block("macOS", subscription_url)
        +
        "<b>Шаг 1.</b> Установите "
        f"<a href=\"{play_url}\">Happ</a> из App Store.\n"
        f"Для региона RU: <a href=\"{ru_play_url}\">Happ (RU)</a>\n\n"
        "<b>Шаг 2.</b> Нажмите ссылку, чтобы профиль импортировался автоматически: "
        f"<a href=\"{escape(auto_url, quote=True)}\">Нажмите для подключения</a>\n\n"
        "<b>Шаг 3.</b> После импорта откройте приложение и нажмите на кнопку включения.\n\n"
    )

    kb = manual_setup_keyboard("macos")
    await cb.answer()

    if not SHOW_VIDEO_INSTRUCTIONS:
        await _send_instruction_without_video(cb, caption, kb)
        return

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_VIDEO)

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
        "2️⃣ Откройте Happ\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите на кнопку включения.\n\n"
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
        "2️⃣ Откройте Happ\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите на кнопку включения.\n\n"
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


@router.callback_query(F.data == "manual_setup:tv")
async def manual_setup_tv(cb: CallbackQuery) -> None:
    text = (
        "<b>Если не получилось подключиться</b>\n\n"
        "<b>Шаг 1.</b> Установите Happ из "
        "<a href=\"https://play.google.com/store/apps/details?id=com.happproxy\">Google Play</a> "
        "или скачайте APK: "
        "<a href=\"https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk\">"
        "Happ.apk</a>\n\n"
        "<b>Шаг 2.</b> Скачайте QR‑код на флешку.\n\n"
        "<b>Шаг 3.</b> На телевизоре откройте Happ → нажмите <i>+</i> → "
        "выберите добавление через QR‑code → укажите файл на флешке.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "manual_setup:windows")
async def manual_setup_windows(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    token = get_token(uid)
    subscription_url = get_subscription_url(uid, token)

    text = (
        "<b>Ручной импорт конфигурации</b>\n\n"
        "1️⃣ Скопируйте ссылку ниже:\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "2️⃣ Откройте Happ\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Добавьте из буфера обмена → выберите сервер → нажмите на кнопку включения.\n\n"
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
        "<b>Не получилось подключиться?</b>\n\n"
        "Если возникли проблемы, напишите в техподдержку или прочитайте ответы на "
        "частые вопросы по кнопкам ниже.\n\n"
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
        "2️⃣ Откройте Happ\n"
        "3️⃣ Нажмите на + в правом верхнем углу\n"
        "4️⃣ Импортируйте из буфера обмена → выберите сервер → нажмите на кнопку включения.\n\n"
    )

    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    await cb.answer()

    await cb.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_faq_back_to_devices_keyboard(),
        disable_web_page_preview=True,
    )

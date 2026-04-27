"""Static OS install instructions adapted from user_bot/handlers/setup.py."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


SUPPORTED_PLATFORMS = {"ios", "android", "macos", "windows", "linux", "tv", "appletv"}


def build_instructions(platform: str, subscription_url: str | None) -> dict[str, Any]:
    platform = (platform or "").strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")

    sub = (subscription_url or "").strip()
    deeplink = f"happ://add/{sub}" if sub else None
    auto_link = (
        f"https://vless-outline.ru/auto/?url={quote(deeplink, safe=':/?=&')}"
        if deeplink
        else None
    )

    common = {
        "platform": platform,
        "subscription_url": sub,
        "deeplink": deeplink,
        "auto_link": auto_link,
    }

    if platform == "ios":
        return {
            **common,
            "title": "Настройка VPN на iPhone",
            "app": {
                "name": "Happ",
                "store_url": "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
                "store_url_ru": "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
            },
            "steps": [
                {"title": "Установите Happ", "description": "Скачайте Happ из App Store. Для региона RU — Happ Plus."},
                {"title": "Импортируйте профиль", "description": "Нажмите кнопку «Подключить» — конфигурация откроется в Happ."},
                {"title": "Включите VPN", "description": "Откройте Happ и нажмите кнопку включения."},
            ],
        }
    if platform == "android":
        return {
            **common,
            "title": "Настройка VPN на Android",
            "app": {
                "name": "Happ",
                "store_url": "https://play.google.com/store/apps/details?id=com.happproxy",
                "apk_url": "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk",
            },
            "steps": [
                {"title": "Установите Happ", "description": "Из Google Play или установите APK напрямую."},
                {"title": "Импортируйте профиль", "description": "Нажмите кнопку «Подключить» — Happ автоматически добавит сервер."},
                {"title": "Включите VPN", "description": "Откройте Happ и активируйте профиль."},
            ],
        }
    if platform == "macos":
        return {
            **common,
            "title": "Настройка VPN на macOS",
            "app": {
                "name": "Happ",
                "store_url": "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
                "store_url_ru": "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
            },
            "steps": [
                {"title": "Установите Happ", "description": "Скачайте Happ из App Store."},
                {"title": "Импортируйте профиль", "description": "Нажмите кнопку «Подключить» — Happ откроется автоматически."},
                {"title": "Включите VPN", "description": "Запустите Happ и активируйте профиль."},
            ],
        }
    if platform == "windows":
        return {
            **common,
            "title": "Настройка VPN на Windows",
            "app": {
                "name": "Happ",
                "download_url": "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe",
            },
            "steps": [
                {"title": "Установите Happ", "description": "Скачайте установщик Happ для Windows."},
                {"title": "Импортируйте профиль", "description": "Нажмите кнопку «Подключить» — Happ автоматически примет конфигурацию."},
                {"title": "Включите VPN", "description": "Откройте Happ и нажмите на кнопку включения."},
            ],
        }
    if platform == "linux":
        return {
            **common,
            "title": "Настройка VPN на Linux (NekoRay)",
            "app": {
                "name": "NekoRay",
                "download_url": "https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-linux64.zip",
                "deb_url": "https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb",
            },
            "steps": [
                {"title": "Скачайте NekoRay", "description": "ZIP или DEB-пакет с GitHub."},
                {"title": "Скопируйте подписку", "description": "Используйте подписочную ссылку и добавьте профиль из буфера обмена в NekoRay."},
                {"title": "Включите TUN-режим", "description": "Активируйте TUN-режим, чтобы пропускать весь трафик через VPN."},
            ],
        }
    if platform == "tv":
        return {
            **common,
            "title": "Настройка VPN на Android TV",
            "app": {
                "name": "Happ",
                "store_url": "https://play.google.com/store/apps/details?id=com.happproxy",
                "apk_url": "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk",
            },
            "steps": [
                {"title": "Установите Happ", "description": "Через Google Play или установите APK с флешки."},
                {"title": "Поделитесь конфигурацией", "description": "С телефона передайте профиль Happ через QR-код."},
                {"title": "Включите VPN", "description": "Выберите конфигурацию на телевизоре и нажмите включение."},
            ],
        }
    return {
        **common,
        "title": "Настройка VPN на Apple TV",
        "app": {
            "name": "Happ for TV",
            "store_url": "https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274",
        },
        "steps": [
            {"title": "Установите Happ", "description": "Скачайте Happ for TV из App Store на Apple TV."},
            {"title": "Поделитесь конфигурацией", "description": "С телефона передайте профиль Happ через QR-код или web-import."},
            {"title": "Включите VPN", "description": "Выберите конфигурацию и активируйте VPN."},
        ],
    }


def build_qr_data_url(data: str) -> str | None:
    if not data:
        return None
    try:
        import base64
        from io import BytesIO

        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    except Exception:
        return None

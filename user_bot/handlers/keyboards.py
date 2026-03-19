import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


SUPPORT_URL = "https://t.me/nitratex1"
FAQ_URL = os.getenv("FAQ_URL", "https://nitratex-company.gitbook.io/kairavpn/")
STATUS_CHANNEL_URL = os.getenv("STATUS_CHANNEL_URL", "https://t.me/nitratex1")


def os_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍎 iOS", callback_data="os:ios"),
                InlineKeyboardButton(text="🤖 Android", callback_data="os:android"),
            ],
            [
                InlineKeyboardButton(text="🖥 Windows", callback_data="os:windows"),
                InlineKeyboardButton(text="💻 macOS", callback_data="os:macos"),
            ],
            [
                InlineKeyboardButton(text="🐧 Linux", callback_data="os:linux"),
                InlineKeyboardButton(text="📺 Android-TV", callback_data="os:tv"),
            ],
            [
                InlineKeyboardButton(text="🍏 Apple TV", callback_data="os:appletv"),
            ],
        ]
    )


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="subscription_tariffs")],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
        ]
    )


def back_to_devices_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К выбору устройства", callback_data="main_menu")]
        ]
    )


def referral_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ℹ️ О скидках", callback_data="referral_info")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
        ]
    )


def help_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL),
                InlineKeyboardButton(text="📖 Частые вопросы", url=FAQ_URL),
            ],
            [
                InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL),
            ],
            [
                InlineKeyboardButton(text="✉️ Поменять email", callback_data="change_email"),
            ],
            [
                InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"),
            ],
        ]
    )


def manual_setup_keyboard(platform: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="😕 Не смогли подключиться?",
                    callback_data=f"manual_setup:{platform}",
                )
            ],
            [
                InlineKeyboardButton(text="🔙 К выбору устройства", callback_data="main_menu"),
            ],
        ]
    )




def support_faq_back_to_devices_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="📖 Частые вопросы", url=FAQ_URL)],
            [InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL)],
            [InlineKeyboardButton(text="🔙 К выбору устройства", callback_data="main_menu")],
        ]
    )


def tariff_menu_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in buttons]
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gift_tariffs_keyboard(tariffs: dict[int, dict[str, int | str]]) -> InlineKeyboardMarkup:
    rows = []
    for months, info in sorted(tariffs.items()):
        text_btn = f"{info['duration']} — {info['price']}₽"
        rows.append([InlineKeyboardButton(text=text_btn, callback_data=f"buy_gift:{months}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gift_payment_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить подарок", url=url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="gift_subscription")],
        ]
    )


def payment_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="subscription_tariffs")],
        ]
    )

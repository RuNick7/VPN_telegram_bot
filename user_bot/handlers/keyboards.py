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
                InlineKeyboardButton(text="📶 Купить LTE Гб", callback_data="lte_gb_menu"),
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
            [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="pay_subscription_menu")],
            [InlineKeyboardButton(text="📶 Купить LTE Гб", callback_data="lte_gb_menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )


def free_mode_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard shown when user's paid subscription has ended.

    The user is on FREE squad (1 free server), so we show:
    - device selectors so they can keep using the free tier;
    - a prominent buy-subscription CTA so they can upgrade.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="pay_subscription_menu")],
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
            [InlineKeyboardButton(text="✍️ Указать пригласившего", callback_data="referral_set_tag")],
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
                InlineKeyboardButton(text="📰 Новости", url=STATUS_CHANNEL_URL),
            ],
            [
                InlineKeyboardButton(text="📶 Купить LTE Гб", callback_data="lte_gb_menu"),
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
            [InlineKeyboardButton(text="📶 Купить LTE Гб", callback_data="lte_gb_menu")],
            [InlineKeyboardButton(text="🔙 К выбору устройства", callback_data="main_menu")],
        ]
    )


def tariff_menu_keyboard(
    buttons: list[tuple[str, str]],
    back_callback: str = "main_menu",
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in buttons]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
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
            [InlineKeyboardButton(text="🔙 Назад", callback_data="pay_subscription_menu")],
        ]
    )


def lte_gb_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5 ГБ — 19₽", callback_data="buy_lte_gb:5")],
            [InlineKeyboardButton(text="10 ГБ — 35₽", callback_data="buy_lte_gb:10")],
            [InlineKeyboardButton(text="25 ГБ — 75₽", callback_data="buy_lte_gb:25")],
            [InlineKeyboardButton(text="50 ГБ — 99₽", callback_data="buy_lte_gb:50")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="pay_menu")],
        ]
    )


def lte_payment_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="lte_gb_menu")],
        ]
    )

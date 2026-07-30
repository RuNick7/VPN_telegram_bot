from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.lte_quota import TRAFFIC_LABEL
from tgvpn_shared.settings import get_settings

_settings = get_settings()
SUPPORT_URL = "https://t.me/nitratex1"
FAQ_URL = _settings.faq_url
STATUS_CHANNEL_URL = _settings.status_channel_url


def os_keyboard() -> InlineKeyboardMarkup:
    """
    Device picker, with renewal offered underneath.

    The renewal row sits apart from the devices deliberately: this keyboard is
    what a user sees right after /start, so it is where they are when they
    realise their subscription is running out -- and making them navigate back
    to a menu to act on that is friction for no reason.
    """
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
            [
                InlineKeyboardButton(text="💳 Продлить", callback_data="renew_menu"),
            ],
        ]
    )


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="subscription_tariffs")],
        ]
    )


def renew_menu_keyboard(*, with_traffic: bool) -> InlineKeyboardMarkup:
    """
    The "Продлить" landing: subscription or extra traffic.

    Traffic is only offered when LTE quotas are switched on -- selling traffic
    that nothing meters would take money for nothing.
    """
    rows = [
        [InlineKeyboardButton(text="💳 Подписка", callback_data="subscription_tariffs")],
    ]
    if with_traffic:
        rows.append(
            [InlineKeyboardButton(text=f"📶 {TRAFFIC_LABEL}", callback_data="lte_packs")]
        )
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def tariff_menu_keyboard(
    buttons: list[tuple[str, str]], *, with_traffic: bool = False
) -> InlineKeyboardMarkup:
    """
    Subscription tariffs, optionally with a link to the traffic packs.

    `with_traffic` is off unless LTE quotas are enabled -- offering to sell
    traffic that isn't metered would take money for nothing.
    """
    rows = [[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in buttons]
    if with_traffic:
        rows.append(
            [InlineKeyboardButton(text=f"📶 {TRAFFIC_LABEL}", callback_data="lte_packs")]
        )
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


def lte_packs_keyboard(packs: dict[int, int]) -> InlineKeyboardMarkup:
    """
    Traffic packs, smallest first, each labelled with what bulk saves.

    Prices are flat -- no referral tiers -- so the only thing that varies is
    pack size, and showing the per-gigabyte saving is what makes the larger
    ones legible at a glance.
    """
    from handlers.utils import traffic_pack_label

    rows = [
        [
            InlineKeyboardButton(
                text=traffic_pack_label(gb, price, packs), callback_data=f"buy_lte:{gb}"
            )
        ]
        for gb, price in sorted(packs.items())
    ]
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lte_payment_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="lte_packs")],
        ]
    )

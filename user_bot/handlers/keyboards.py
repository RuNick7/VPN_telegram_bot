from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.lte_quota import TRAFFIC_LABEL, TRAFFIC_TOPUP_CALLBACK
from tgvpn_shared.settings import get_settings

_settings = get_settings()
SUPPORT_URL = _settings.support_url
FAQ_URL = _settings.faq_url
STATUS_CHANNEL_URL = _settings.status_channel_url
VPNCHECK_DOWNLOAD_URL = _settings.vpncheck_download_url.strip()
# The customer cabinet on the website; empty when no site is configured, and
# then no button points at it.
_SITE = _settings.web_base_url.strip().rstrip("/")
CABINET_URL = f"{_SITE}/app" if _SITE else ""

# Button colours (Bot API `style`). Telegram releases from before February 2026
# draw these as ordinary buttons, so a colour may only ever add emphasis --
# never carry meaning a plain button would lose.
GREEN = "success"
BLUE = "primary"
RED = "danger"

# The menu screens. `connect` opens the device picker, which used to be the
# main menu itself.
CONNECT_CALLBACK = "connect"
REFERRAL_CALLBACK = "referral"
CHANNEL_OK_CALLBACK = "channel_ok"


def _check_servers_row() -> list[list[InlineKeyboardButton]]:
    """
    The server-check program, where people go when something does not work.
    Its report goes straight into a support ticket. No row without a download
    link: a button that leads nowhere is worse than none.
    """
    if not VPNCHECK_DOWNLOAD_URL:
        return []
    return [[InlineKeyboardButton(text="🩺 Проверить серверы", url=VPNCHECK_DOWNLOAD_URL)]]


def main_menu_keyboard(*, renew_urgent: bool = False) -> InlineKeyboardMarkup:
    """
    The main menu under the subscription summary.

    «Подключиться» is the one most people came for, so it is green and on its
    own row. «Продлить» turns red when the subscription has three days or less
    left, or has run out -- the moment the button matters is exactly the
    moment it should be hard to miss.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Подключиться", callback_data=CONNECT_CALLBACK, style=GREEN
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Продлить",
                    callback_data="renew_menu",
                    style=RED if renew_urgent else BLUE,
                )
            ],
            [
                InlineKeyboardButton(text="🎁 Реф. программа", callback_data=REFERRAL_CALLBACK),
                InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
            ],
            *(
                [[InlineKeyboardButton(text="🌐 Личный кабинет на сайте", url=CABINET_URL)]]
                if CABINET_URL
                else []
            ),
        ]
    )


def channel_prompt_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    """
    The one-time channel invitation. «Я подписался» is not checked against
    the channel: it opens the menu whatever the answer.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_url)],
            [
                InlineKeyboardButton(
                    text="✅ Я подписался", callback_data=CHANNEL_OK_CALLBACK, style=GREEN
                )
            ],
        ]
    )


def os_keyboard() -> InlineKeyboardMarkup:
    """
    The device picker behind «Подключиться».

    Renewal no longer sits here: it has its own button in the main menu, one
    tap back.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍎 iPhone / iPad", callback_data="os:ios"),
                InlineKeyboardButton(text="🤖 Android", callback_data="os:android"),
            ],
            [
                InlineKeyboardButton(text="🖥 Windows", callback_data="os:windows"),
                InlineKeyboardButton(text="💻 macOS", callback_data="os:macos"),
            ],
            [
                InlineKeyboardButton(text="🐧 Linux", callback_data="os:linux"),
                InlineKeyboardButton(text="📺 Android TV", callback_data="os:tv"),
            ],
            [
                InlineKeyboardButton(text="🍏 Apple TV", callback_data="os:appletv"),
            ],
            [
                InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"),
            ],
        ]
    )


def pay_keyboard() -> InlineKeyboardMarkup:
    """Shown only when there is no access left at all, hence red."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Продлить подписку", callback_data="subscription_tariffs", style=RED
                )
            ],
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
            [InlineKeyboardButton(text=f"📶 {TRAFFIC_LABEL}", callback_data=TRAFFIC_TOPUP_CALLBACK)]
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
            [InlineKeyboardButton(text="🔙 К выбору устройства", callback_data=CONNECT_CALLBACK)]
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
    """
    «❓ Помощь»: support on a row of its own, the rest in pairs.

    Support is what most people open this menu for, so it comes first and is
    the one coloured button. The optional two -- the server check and the
    cabinet, each shown only when configured -- share a row, so turning one
    off does not leave a hole in another pair.
    """
    optional = []
    if VPNCHECK_DOWNLOAD_URL:
        optional.append(InlineKeyboardButton(text="🩺 Проверить серверы", url=VPNCHECK_DOWNLOAD_URL))
    if CABINET_URL:
        optional.append(InlineKeyboardButton(text="🌐 Личный кабинет", url=CABINET_URL))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL, style=BLUE)],
            [
                InlineKeyboardButton(text="📖 Частые вопросы", url=FAQ_URL),
                InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL),
            ],
            *([optional] if optional else []),
            [
                InlineKeyboardButton(text="📧 Поменять email", callback_data="change_email"),
                InlineKeyboardButton(text="📄 Документы", callback_data="documents"),
            ],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
        ]
    )


def manual_setup_keyboard(
    platform: str, *, import_url: str = "", region_help: bool = False
) -> InlineKeyboardMarkup:
    """
    Buttons under one device's instructions.

    `import_url` is the https:// wrapper around `incy://import/…`. It is a
    button only when we have one: Telegram refuses a URL button with an app
    scheme outright, so without our own redirect the link stays in the text.
    `region_help` adds the App Store region guide, for the Apple devices that
    install from a store where the Russian Apple ID cannot see Incy.
    """
    rows = []
    if import_url:
        rows.append(
            [InlineKeyboardButton(text="📲 Добавить в Incy", url=import_url, style=GREEN)]
        )
    if region_help:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔍 Не нахожу Incy в App Store",
                    callback_data=f"region_help:{platform}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="😕 Не получилось подключиться?",
                callback_data=f"manual_setup:{platform}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=CONNECT_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_help_keyboard(platform: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К инструкции", callback_data=f"os:{platform}")],
        ]
    )


def support_faq_back_to_devices_keyboard() -> InlineKeyboardMarkup:
    """
    The "не смогли подключиться" menu.

    The two self-service actions sit here rather than in the main menu because
    this is where someone who cannot connect already is -- and a device over
    the limit or a link that leaked are two of the reasons they got here.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="📖 Частые вопросы", url=FAQ_URL)],
            [InlineKeyboardButton(text="📢 Канал бота", url=STATUS_CHANNEL_URL)],
            *_check_servers_row(),
            [
                InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_devices"),
                InlineKeyboardButton(
                    text="🔄 Сбросить ссылку", callback_data="sub_reset", style=RED
                ),
            ],
            [InlineKeyboardButton(text="🔙 К выбору устройства", callback_data=CONNECT_CALLBACK)],
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
            [InlineKeyboardButton(text=f"📶 {TRAFFIC_LABEL}", callback_data=TRAFFIC_TOPUP_CALLBACK)]
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
            [InlineKeyboardButton(text="🎁 Оплатить подарок", url=url, style=GREEN)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="gift_subscription")],
        ]
    )


def payment_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url, style=GREEN)],
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
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url, style=GREEN)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=TRAFFIC_TOPUP_CALLBACK)],
        ]
    )

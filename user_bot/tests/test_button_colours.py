"""
Button colours follow their meaning, one rule per colour:

    MAIN    the screen's main action -- «Подключиться», «Продлить» while it is
            not urgent, «Оплатить»
    DONE    a step completed or confirmed -- «Я подписался», «Добавить в Incy»
    URGENT  irreversible actions and urgent renewal -- «Сбросить ссылку»,
            removing a device, «Продлить» near or past the end
    none    everything else, support included
"""

import pytest

import handlers.devices as devices
import handlers.keyboards as keyboards
from handlers.keyboards import DONE, MAIN, URGENT


def _style(markup, *, text=None, callback=None):
    for row in markup.inline_keyboard:
        for button in row:
            if (text and text in button.text) or (callback and button.callback_data == callback):
                return button.style
    raise AssertionError(f"no button {text or callback}")


def test_the_three_colours_are_telegrams_three_styles():
    # Telegram has no violet: "primary" is the main-action style, blue by
    # default and tinted to the chat theme by the apps that do so.
    assert (MAIN, DONE, URGENT) == ("primary", "success", "danger")


@pytest.mark.parametrize(
    "markup, text",
    [
        (keyboards.payment_keyboard("https://pay.example"), "Перейти к оплате"),
        (keyboards.lte_payment_keyboard("https://pay.example"), "Перейти к оплате"),
        (keyboards.gift_payment_keyboard("https://pay.example"), "Оплатить подарок"),
    ],
)
def test_paying_is_the_main_action(markup, text):
    assert _style(markup, text=text) == MAIN


def test_confirmed_steps_are_green():
    assert _style(keyboards.channel_prompt_keyboard("https://t.me/c"), text="Я подписался") == DONE
    setup = keyboards.manual_setup_keyboard("ios", import_url="https://kairavpn.pro/auto?url=x")
    assert _style(setup, text="Добавить в Incy") == DONE


def test_irreversible_and_urgent_are_red():
    assert _style(keyboards.support_faq_back_to_devices_keyboard(), callback="sub_reset") == URGENT
    assert _style(keyboards.pay_keyboard(), callback="subscription_tariffs") == URGENT
    confirm = devices._confirm_keyboard("device_del_ok:abc", confirm_text="❌ Отключить")
    assert _style(confirm, callback="device_del_ok:abc") == URGENT


def test_the_expiry_reminder_renews_in_red():
    from utils.reminders import pay_kb

    assert _style(pay_kb, callback="subscription_tariffs") == URGENT


def test_support_and_navigation_stay_uncoloured():
    help_menu = keyboards.help_menu_keyboard()
    assert _style(help_menu, text="Тех. поддержка") is None
    assert _style(help_menu, callback="main_menu") is None
    assert _style(keyboards.os_keyboard(), callback="main_menu") is None
    setup = keyboards.manual_setup_keyboard("ios", region_help=True)
    assert _style(setup, text="Не нахожу Incy") is None
    assert _style(setup, text="Назад") is None

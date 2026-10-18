"""
«🩺 Проверить серверы» leads to the vpncheck download, from both places
someone with a problem ends up: the help menu and «не смогли подключиться».
"""

import pytest

from handlers import keyboards


def _urls(markup) -> list[str]:
    return [button.url for row in markup.inline_keyboard for button in row if button.url]


@pytest.mark.parametrize("menu", [keyboards.help_menu_keyboard, keyboards.support_faq_back_to_devices_keyboard])
def test_the_button_is_there_with_a_download_link(monkeypatch, menu):
    monkeypatch.setattr(keyboards, "VPNCHECK_DOWNLOAD_URL", "https://example.com/vpncheck/")
    assert "https://example.com/vpncheck/" in _urls(menu())

    monkeypatch.setattr(keyboards, "VPNCHECK_DOWNLOAD_URL", "")
    assert not any("vpncheck" in url for url in _urls(menu()))

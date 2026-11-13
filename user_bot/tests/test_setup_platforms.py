"""
The platform table that replaced 14 near-identical setup handlers.

The risk in collapsing them is a platform quietly losing a piece of its
instructions, so these assert the contract each spec has to satisfy rather
than the exact copy.
"""

import re
from types import SimpleNamespace

import pytest

import handlers.setup as setup
from handlers.keyboards import os_keyboard
from handlers.setup import PLATFORMS, _auto_import_link, import_button_url

SUBSCRIPTION_URL = "https://panel.example.com/sub/abc123"


def test_every_device_button_has_a_spec():
    """
    A device button with no spec renders nothing when tapped.

    This is the check that would have caught a platform being dropped during
    the collapse into the table.
    """
    offered = {
        button.callback_data.split(":", 1)[1]
        for row in os_keyboard().inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("os:")
    }
    assert offered == set(PLATFORMS)


@pytest.mark.parametrize("key", sorted(PLATFORMS))
def test_instruction_and_manual_render_non_empty_html(key):
    spec = PLATFORMS[key]
    url = SUBSCRIPTION_URL if spec.needs_url else ""
    assert spec.instruction(url).strip()
    assert spec.manual(SUBSCRIPTION_URL if spec.manual_needs_url else "").strip()


@pytest.mark.parametrize("key", sorted(PLATFORMS))
def test_platforms_that_need_a_url_actually_embed_it(key):
    """`needs_url` must mean the URL shows up, or we fetch it for nothing."""
    spec = PLATFORMS[key]
    if not spec.needs_url:
        return
    assert SUBSCRIPTION_URL in spec.instruction(SUBSCRIPTION_URL)


@pytest.mark.parametrize("key", sorted(PLATFORMS))
def test_manual_needs_url_matches_what_it_renders(key):
    spec = PLATFORMS[key]
    if not spec.manual_needs_url:
        # Must not depend on the URL -- it is called with an empty string.
        assert spec.manual("").strip()
        return
    assert SUBSCRIPTION_URL in spec.manual(SUBSCRIPTION_URL)


def test_tv_platforms_skip_the_panel_round_trip():
    """TVs are paired from a phone, so they never need the user's own URL."""
    for key in ("tv", "appletv"):
        assert PLATFORMS[key].needs_url is False
        assert PLATFORMS[key].manual_needs_url is False


def test_video_aliases_point_at_real_files():
    from precache_videos import VIDEOS

    for key, spec in PLATFORMS.items():
        if spec.video_alias:
            assert spec.video_alias in VIDEOS, f"{key} references unknown video {spec.video_alias}"


def test_auto_import_link_percent_encodes_the_deep_link(monkeypatch):
    """
    The `incy://` deep link is a query parameter, so its own separators have
    to be encoded -- only the Windows handler got this right before Phase 2.

    The wrapper is pinned rather than read from the environment. Encoding only
    happens on the wrapped path, so without WEB_BASE_URL set this asserted
    nothing and passed -- and with it unset, failed. Which of the two you got
    depended on the machine.
    """
    monkeypatch.setattr(setup, "_auto_import_wrapper", lambda: "https://kairavpn.pro/auto?url=")

    link = _auto_import_link("https://panel.example.com/sub/a b?x=1#frag")
    assert " " not in link
    assert "%20" in link


def test_the_redirect_is_our_own_site(monkeypatch):
    """
    It used to be somebody else's server, so every customer's subscription URL
    -- which is the whole credential -- went through a third party to reach
    their own phone.
    """
    monkeypatch.setattr(setup, "_auto_import_wrapper", lambda: "https://kairavpn.pro/auto?url=")

    link = _auto_import_link(SUBSCRIPTION_URL)

    # `:` and `/` are left legible: neither has a meaning inside a query, so
    # encoding them would only make the link harder to read in a support chat.
    assert link == f"https://kairavpn.pro/auto?url=incy://import/{SUBSCRIPTION_URL}"


def test_an_ampersand_cannot_cut_the_link_in_half(monkeypatch):
    """
    `&` was left unencoded, and one in a subscription URL would have ended the
    query parameter there -- handing the app the first half of the address.
    """
    monkeypatch.setattr(setup, "_auto_import_wrapper", lambda: "https://kairavpn.pro/auto?url=")

    link = _auto_import_link("https://panel.example.com/sub/tok?a=1&b=2")

    assert "&" not in link.split("?url=", 1)[1]
    assert "%26" in link


def test_the_wrapper_follows_the_configured_site(monkeypatch):
    monkeypatch.setattr(
        setup, "get_settings", lambda: SimpleNamespace(web_base_url="https://kairavpn.pro/")
    )
    assert setup._auto_import_wrapper() == "https://kairavpn.pro/auto?url="


def test_without_a_site_the_bare_deep_link_is_used(monkeypatch):
    """
    There is nowhere of ours to point at, and a link to nowhere is worse than
    one that works everywhere except inside Telegram's own browser.
    """
    monkeypatch.setattr(setup, "get_settings", lambda: SimpleNamespace(web_base_url="  "))

    assert _auto_import_link(SUBSCRIPTION_URL) == f"incy://import/{SUBSCRIPTION_URL}"


def test_phone_and_desktop_platforms_share_the_same_manual_fallback():
    """The clipboard-import fallback is one function, not four near-copies."""
    keys = ("android", "ios", "windows", "macos")
    rendered = {PLATFORMS[key].manual(SUBSCRIPTION_URL) for key in keys}
    assert len(rendered) == 1


def test_desktop_downloads_follow_incys_fixed_latest_release():
    """
    Not /releases/latest/download/: the newest release in Incy's repository is
    often an Android-only one, and a desktop file name would 404 there. The
    project re-uploads every file under the fixed tag `latest` instead.
    """
    for key in ("windows", "macos", "linux"):
        text = PLATFORMS[key].instruction("https://sub.kairavpn.pro/abc")
        links = re.findall(r'href="(https://github[^"]+)"', text)
        assert len(links) >= 2, key
        for href in links:
            assert re.fullmatch(
                r"https://github\.com/INCY-DEV/incy-platforms/releases/"
                r"(download/latest/[\w.-]+|tag/latest)",
                href,
            ), href


@pytest.mark.parametrize("key", sorted(PLATFORMS))
def test_no_instruction_mentions_an_app_we_dropped(key):
    spec = PLATFORMS[key]
    text = spec.instruction(SUBSCRIPTION_URL) + spec.manual(SUBSCRIPTION_URL)
    assert not re.search(r"happ|koala|nekoray", text, re.IGNORECASE), key


def test_app_store_links_name_the_real_incy():
    """The Russian store carries apps called Incy from other sellers."""
    texts = [spec.instruction(SUBSCRIPTION_URL) for spec in PLATFORMS.values()]
    texts.append(setup.REGION_HELP_HTML)
    links = [h for t in texts for h in re.findall(r'href="([^"]+)"', t) if "apps.apple.com" in h]
    assert links
    assert set(links) == {"https://apps.apple.com/us/app/incy/id6756943388"}


def test_region_help_is_offered_where_the_app_store_is_the_only_way():
    """iPhone and Apple TV install from the App Store; the Mac has a .dmg."""
    offered = {key for key, spec in PLATFORMS.items() if spec.region_help}
    assert offered == {"ios", "appletv"}
    assert "LLC ITDEV" in setup.REGION_HELP_HTML


def test_import_button_only_exists_with_our_own_redirect(monkeypatch):
    """Telegram refuses a URL button whose address is an app scheme."""
    monkeypatch.setattr(setup, "_auto_import_wrapper", lambda: "")
    assert import_button_url(SUBSCRIPTION_URL) == ""

    monkeypatch.setattr(setup, "_auto_import_wrapper", lambda: "https://kairavpn.pro/auto?url=")
    url = import_button_url(SUBSCRIPTION_URL)
    assert url == f"https://kairavpn.pro/auto?url=incy://import/{SUBSCRIPTION_URL}"
    # The text then points at the button rather than carrying a second link.
    assert "Добавить в Incy" in PLATFORMS["ios"].instruction(SUBSCRIPTION_URL)
    assert "auto?url=" not in PLATFORMS["ios"].instruction(SUBSCRIPTION_URL)

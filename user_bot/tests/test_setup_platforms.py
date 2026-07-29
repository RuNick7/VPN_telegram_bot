"""
The platform table that replaced 14 near-identical setup handlers.

The risk in collapsing them is a platform quietly losing a piece of its
instructions, so these assert the contract each spec has to satisfy rather
than the exact copy.
"""

import pytest

from handlers.keyboards import os_keyboard
from handlers.setup import PLATFORMS, _auto_import_link

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


def test_auto_import_link_percent_encodes_the_deep_link():
    """
    The `happ://` deep link is a query parameter, so its own separators have
    to be encoded -- only the Windows handler got this right before Phase 2.
    """
    link = _auto_import_link("https://panel.example.com/sub/a b?x=1#frag")
    assert " " not in link
    assert "%20" in link
    assert link.startswith("https://vless-outline.ru/auto/?url=")


def test_happ_platforms_share_the_same_manual_fallback():
    """The clipboard-import fallback is one function, not four near-copies."""
    happ = ("android", "ios", "windows", "macos")
    rendered = {PLATFORMS[key].manual(SUBSCRIPTION_URL) for key in happ}
    assert len(rendered) == 1

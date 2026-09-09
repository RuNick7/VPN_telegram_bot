"""
The gift link.

A gift used to be a promo code and nothing else, redeemable only in the bot —
which made it useless to exactly the person most likely to be handed one:
somebody who has never used Telegram. The link is a second way to reach the
*same* code, so a gift can still only be redeemed once whichever route the
recipient takes.
"""

import pytest
from tgvpn_shared.settings import Settings


def settings(base_url: str = "https://cabinet.example.com") -> Settings:
    return Settings(web_base_url=base_url)


def test_a_gift_link_points_at_the_site():
    assert settings().gift_link("GIFT-ABC123") == "https://cabinet.example.com/gift/GIFT-ABC123"


def test_a_trailing_slash_does_not_double_up():
    assert settings("https://cabinet.example.com/").gift_link("X") == (
        "https://cabinet.example.com/gift/X"
    )


@pytest.mark.parametrize("base", ["", "   "])
def test_no_site_means_no_link(base):
    """
    The bot then offers only the code. That path has always worked and must
    not start depending on a website that may not be deployed yet.
    """
    assert settings(base).gift_link("GIFT-ABC123") == ""


def test_the_code_is_carried_verbatim():
    """
    The recipient's browser sends it back to /api/promo/redeem, which upper-
    cases and trims it — so the link must not mangle it on the way out.
    """
    assert settings().gift_link("GIFT-9Z8Y7X").endswith("/gift/GIFT-9Z8Y7X")

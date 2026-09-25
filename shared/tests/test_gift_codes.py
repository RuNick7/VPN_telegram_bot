"""
Gift codes are bearer credentials: whoever holds one gets the subscription it
was paid for. These pin the properties that makes them safe to hand out.
"""

import re
import string

from tgvpn_shared.db.promo import _GIFT_ALPHABET, generate_gift_code


def test_codes_are_unpredictable():
    """
    Not a statistical test -- it cannot be. What it pins is that two calls
    differ, which `random.seed(0)` reproducibility would eventually break, and
    that the space is wide enough to matter.
    """
    codes = {generate_gift_code() for _ in range(500)}
    assert len(codes) == 500


def test_the_alphabet_has_no_confusable_characters():
    """A code gets read off a screen, typed into a phone, often dictated."""
    for confusable in "IOL01":
        assert confusable not in _GIFT_ALPHABET


def test_every_character_is_from_the_alphabet():
    body = generate_gift_code().removeprefix("GIFT-")
    assert set(body) <= set(_GIFT_ALPHABET)


def test_the_code_is_long_enough_to_not_be_guessed():
    # 31 symbols, 10 places: about 50 bits. Brute-forcing that through an HTTP
    # endpoint or a Telegram chat is not a thing, rate limits or not.
    assert len(generate_gift_code().removeprefix("GIFT-")) == 10
    assert len(_GIFT_ALPHABET) >= 31


def test_the_prefix_is_kept_so_support_recognises_one_on_sight():
    assert generate_gift_code().startswith("GIFT-")


def test_a_generated_code_survives_the_uppercasing_every_entry_path_does():
    code = generate_gift_code()
    assert code.upper() == code

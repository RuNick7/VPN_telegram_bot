"""
The rules both bots and the website share for server-check report codes.

The hash vectors are the same ones web/internal/support/diagnostics_test.go
pins: user_bot stores the hash, the website looks a code up by it, and a
drift between the two would make every code the bot hands out fail.
"""

import re

from tgvpn_shared.support_diagnostics import (
    CODE_ALPHABET,
    COLLECTED,
    consent_text,
    generate_code,
    granted_text,
    hash_code,
    normalize_code,
)


def test_hash_matches_the_website():
    assert hash_code("ABCD-EFGH-JKLM").hex() == "3f63d25fcb898ecfd6c2e2322bfdb11f44fe17dd0dc359e70b7246224bb223e9"
    assert hash_code("2345 6789 zzzz").hex() == "549e28949b20b47515287b51562051f165bc799dd16dc959361dab3370bbc95d"


def test_codes_are_made_to_be_read_off_a_phone():
    for _ in range(200):
        code = generate_code()
        assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code)
        assert not set(code.replace("-", "")) - set(CODE_ALPHABET)
        assert normalize_code(code) == code.replace("-", "")
    assert len({generate_code() for _ in range(200)}) == 200


def test_normalize_takes_what_people_type_and_nothing_else():
    assert normalize_code(" abcd-efgh jklm ") == "ABCDEFGHJKLM"
    for bad in ("", "ABCD-EFGH", "ABCD-EFGH-JKL0", "ABCD-EFGH-JKLI", "ABCD_EFGH_JKLM", None):
        assert normalize_code(bad) is None


def test_the_question_says_what_is_collected_and_what_is_not():
    text = consent_text(7, "Не <работает>")
    assert COLLECTED in text
    assert "вырезаются" in text and "IP-адрес" in text
    assert "Без вашего согласия ничего не собирается" in text
    # The subject is the customer's own text and the message is HTML.
    assert "Не &lt;работает&gt;" in text


def test_the_answer_carries_the_code_and_where_to_get_the_program():
    text = granted_text(7, "Тема", "ABCD-EFGH-JKLM", "https://example.com/vpncheck/", 1_800_000_000)
    assert "<code>ABCD-EFGH-JKLM</code>" in text
    assert "https://example.com/vpncheck/" in text
    assert "Выключите VPN" in text

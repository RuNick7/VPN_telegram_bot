"""
Browsing promo codes before deleting one.

Deletion used to be "type the code": the only way to remove a code was to
already know it exists and how it is spelled. Nothing in the bot ever listed
them, so a code created months ago by another operator was undiscoverable, and
`creator_id` -- the column that would say whose it was -- was never filled in
for codes made here at all.
"""

from datetime import datetime, timezone

from app.handlers.admin.promo import (
    CALLBACK_LIMIT,
    creator_of,
    format_promo_page,
    promo_callback,
    promo_label,
)


def promo(**overrides) -> dict:
    """A row as `list_promo_codes_page` returns it."""
    row = {
        "code": "SUMMER24",
        "type": "days",
        "value": 30,
        "one_time": True,
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "creator_id": None,
        "creator_tag": None,
        "creator_email": None,
        "creator_telegram_id": None,
        "used_count": 0,
    }
    row.update(overrides)
    return row


# -- who made it -----------------------------------------------------------


def test_an_operators_code_is_attributed_to_their_telegram_id():
    """
    The common case, and the one that had no answer before.

    An operator creating a code in admin_bot usually has no customer row, so
    the join finds nothing and the raw ID is the only handle there is. It still
    names them, which "—" did not.
    """
    assert creator_of(promo(creator_id=427)) == "tg:427"


def test_a_customers_gift_is_attributed_to_their_nickname():
    assert creator_of(promo(creator_id=427, creator_tag="masha")) == "@masha"


def test_a_website_buyer_is_attributed_to_their_address():
    """No Telegram at all -- the account kind the site creates."""
    assert creator_of(promo(creator_email="buyer@example.com")) == "buyer@example.com"


def test_a_code_from_before_authorship_was_recorded_says_so():
    """Rather than blaming whoever happens to be listed nearby."""
    assert creator_of(promo()) == "—"


# -- the buttons -----------------------------------------------------------


def test_a_button_says_what_the_code_grants():
    assert promo_label(promo()) == "SUMMER24 — 30 дн."


def test_a_spent_one_time_code_is_marked_as_spent():
    """The one thing that decides whether deleting it costs anything."""
    assert "✔️" in promo_label(promo(one_time=True, used_count=1))


def test_a_reusable_code_shows_how_many_times_it_went_out():
    assert "×7" in promo_label(promo(one_time=False, used_count=7))


def test_a_code_too_long_to_address_gets_no_button():
    """
    Telegram rejects callback data over 64 bytes and codes are free text, so
    one long code would otherwise fail the whole keyboard rather than itself.
    `picker_keyboard` drops an item whose callback is None; typing the code
    still deletes it.
    """
    assert promo_callback(promo(code="X" * 200)) is None
    assert len(promo_callback(promo()).encode()) <= CALLBACK_LIMIT


def test_a_cyrillic_code_is_measured_in_bytes_not_characters():
    """The limit Telegram enforces is bytes, and these are two apiece."""
    assert promo_callback(promo(code="Я" * 30)) is None


# -- the page --------------------------------------------------------------


def test_the_page_shows_what_a_button_cannot():
    text = format_promo_page([promo(creator_id=427, used_count=0)], page=1, total=1)
    assert "SUMMER24" in text
    assert "30 дн." in text
    assert "одноразовый" in text
    assert "tg:427" in text
    assert "01.08.2026" in text


def test_a_disabled_code_is_visibly_disabled():
    """It grants nothing, which is not obvious from the row otherwise."""
    assert "выключен" in format_promo_page([promo(is_active=False)], page=1, total=1)


def test_a_code_cannot_smuggle_markup_into_the_page():
    """
    The page is sent as HTML and a code is typed by an operator. An unescaped
    `<b>` is a broken message; aiogram raises on it and the whole list fails to
    render, which is a list nobody can use to find anything.
    """
    text = format_promo_page([promo(code="<b>x</b>")], page=1, total=1)
    assert "<b>x</b>" not in text
    assert "&lt;b&gt;x&lt;/b&gt;" in text

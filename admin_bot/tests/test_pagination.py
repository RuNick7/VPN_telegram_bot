"""The generic pagination helper that four admin list flows now share."""

import pytest

from app.handlers.admin.pagination import (
    list_page_keyboard,
    max_page,
    nav_row,
    parse_page,
    picker_keyboard,
    slice_page,
)


@pytest.mark.parametrize(
    "total, size, expected",
    [
        (0, 10, 1),   # an empty list still has one (empty) page
        (1, 10, 1),
        (10, 10, 1),
        (11, 10, 2),
        (495, 20, 25),
    ],
)
def test_max_page(total, size, expected):
    assert max_page(total, size) == expected


def test_max_page_survives_a_zero_size():
    """Page sizes are module constants, but a 0 must degrade, not divide by zero."""
    assert max_page(100, 0) >= 1


def test_nav_row_clamps_at_both_ends():
    first = nav_row("p", 1, 50, 10)
    assert first[0].callback_data == "p:1"   # ⬅️ on page 1 stays on page 1
    assert first[2].callback_data == "p:2"

    last = nav_row("p", 5, 50, 10)
    assert last[0].callback_data == "p:4"
    assert last[2].callback_data == "p:5"    # ➡️ on the last page stays put


def test_nav_row_middle_button_opens_goto_or_is_inert():
    assert nav_row("p", 2, 50, 10, goto_callback_data="p:goto")[1].callback_data == "p:goto"
    assert nav_row("p", 2, 50, 10)[1].callback_data == "noop"
    assert nav_row("p", 2, 50, 10)[1].text == "2/5"


@pytest.mark.parametrize(
    "data, expected",
    [
        ("admin:stats:page:7", 7),
        ("admin:edit_user:list:1", 1),
        # Non-numeric tails fall back to page 1 rather than raising: the goto
        # callback shares a prefix with the page callbacks.
        ("admin:edit_user:list:goto", 1),
        ("admin:stats", 1),
        ("admin:stats:page:0", 1),
        ("admin:stats:page:-3", 1),
    ],
)
def test_parse_page(data, expected):
    assert parse_page(data) == expected


def test_slice_page_returns_the_right_window():
    items = [{"i": i} for i in range(25)]
    chunk, last = slice_page(items, 2, 10)
    assert [c["i"] for c in chunk] == list(range(10, 20))
    assert last == 3


def test_slice_page_clamps_out_of_range_pages():
    """A stale keyboard from a since-shrunken list must not render nothing."""
    items = [{"i": i} for i in range(5)]
    assert [c["i"] for c in slice_page(items, 99, 10)[0]] == [0, 1, 2, 3, 4]
    assert [c["i"] for c in slice_page(items, 0, 10)[0]] == [0, 1, 2, 3, 4]


def test_picker_keyboard_skips_items_without_a_callback():
    items = [{"username": "a", "uuid": "u1"}, {"username": "b"}, {"username": "c", "uuid": "u3"}]
    keyboard = picker_keyboard(
        items,
        label=lambda u: u["username"],
        item_callback=lambda u: f"pick:{u['uuid']}" if u.get("uuid") else None,
        prefix="p",
        page=1,
        total=3,
        size=10,
    )
    item_rows = keyboard.inline_keyboard[:-2]  # last two rows are nav + menu
    assert [row[0].text for row in item_rows] == ["a", "c"]
    assert [row[0].callback_data for row in item_rows] == ["pick:u1", "pick:u3"]


def test_picker_keyboard_ends_with_nav_then_menu():
    keyboard = picker_keyboard(
        [{"uuid": "u1"}],
        label=lambda u: "x",
        item_callback=lambda u: "pick:u1",
        prefix="p",
        page=1,
        total=1,
        size=10,
    )
    nav, menu = keyboard.inline_keyboard[-2], keyboard.inline_keyboard[-1]
    assert [b.text for b in nav] == ["⬅️", "1/1", "➡️"]
    assert menu[0].callback_data == "admin:menu"


def test_list_page_keyboard_puts_extra_rows_between_items_and_nav():
    """Multi-select flows slot their "Готово" button in here."""
    from aiogram.types import InlineKeyboardButton

    done = InlineKeyboardButton(text="✅ Готово", callback_data="done")
    keyboard = list_page_keyboard(
        [{"uuid": "u1"}, {"uuid": "u2"}],
        page=1,
        size=10,
        prefix="p",
        label=lambda item: item["uuid"],
        item_callback=lambda item: f"toggle:{item['uuid']}",
        extra_rows=[[done]],
    )
    texts = [row[0].text for row in keyboard.inline_keyboard]
    assert texts == ["u1", "u2", "✅ Готово", "⬅️", "◀️ В меню"]

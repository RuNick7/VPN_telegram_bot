"""
Generic paginated list/picker for admin flows.

The create/edit/delete/stats user flows -- and the host flows in
`hosts_quick.py` -- each hand-rolled the same trio: render a page, offer
prev/next/goto navigation, and (for pickers) one button per item. Four copies
of the same arithmetic, four callback-prefix conventions, four `int(...)`
parsers.

This module owns that shape once. A caller supplies a `PagedView` describing
where its data comes from and how to draw a page; the nav keyboard, the
"go to page N" prompt, and the bounds checking come from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.states.admin import UserListPageState

MENU_BUTTON = InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")


def max_page(total: int, size: int) -> int:
    """Page count for `total` items at `size` per page; never below 1."""
    return max(1, (total + max(1, size) - 1) // max(1, size))


def slice_page(
    items: list[dict[str, Any]], page: int, size: int
) -> tuple[list[dict[str, Any]], int]:
    """
    One page out of an in-memory list, as `(chunk, last_page)`.

    For lists the panel returns whole (hosts, inbounds, nodes, squads) rather
    than page by page. `page` is clamped into range, so a stale keyboard from
    a shrunken list can't render an empty page.
    """
    last = max_page(len(items), size)
    page = max(1, min(page, last))
    start = (page - 1) * size
    return items[start : start + size], last


def nav_row_for_pages(
    prefix: str,
    page: int,
    last_page: int,
    *,
    goto_callback_data: str | None = None,
) -> list[InlineKeyboardButton]:
    """`⬅️ | 3/17 | ➡️` given a page count rather than an item count."""
    return [
        InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{max(1, page - 1)}"),
        InlineKeyboardButton(text=f"{page}/{last_page}", callback_data=goto_callback_data or "noop"),
        InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{min(last_page, page + 1)}"),
    ]


def nav_row(
    prefix: str,
    page: int,
    total: int,
    size: int,
    *,
    goto_callback_data: str | None = None,
) -> list[InlineKeyboardButton]:
    """`⬅️ | 3/17 | ➡️`, where the middle button opens the goto prompt."""
    return nav_row_for_pages(
        prefix, page, max_page(total, size), goto_callback_data=goto_callback_data
    )


def nav_keyboard(
    prefix: str,
    page: int,
    total: int,
    size: int,
    *,
    goto_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """Navigation only -- for text views with nothing to pick."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav_row(prefix, page, total, size, goto_callback_data=goto_callback_data),
            [MENU_BUTTON],
        ]
    )


def picker_keyboard(
    items: list[dict[str, Any]],
    *,
    label: Callable[[dict[str, Any]], str],
    item_callback: Callable[[dict[str, Any]], str | None],
    prefix: str,
    page: int,
    total: int,
    size: int,
    goto_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """One button per item, then navigation. Items with no callback are skipped."""
    rows = []
    for item in items:
        callback_data = item_callback(item)
        if callback_data:
            rows.append([InlineKeyboardButton(text=label(item), callback_data=callback_data)])
    rows.append(nav_row(prefix, page, total, size, goto_callback_data=goto_callback_data))
    rows.append([MENU_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def list_page_keyboard(
    items: list[dict[str, Any]],
    page: int,
    size: int,
    *,
    prefix: str,
    label: Callable[[dict[str, Any]], str],
    item_callback: Callable[[dict[str, Any]], str | None],
    extra_rows: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """
    Picker over an in-memory list: item buttons, extra rows, navigation, menu.

    `extra_rows` sits between the items and the navigation -- that's where a
    multi-select flow puts its "✅ Готово" button.
    """
    chunk, last = slice_page(items, page, size)
    rows = []
    for item in chunk:
        callback_data = item_callback(item)
        if callback_data:
            rows.append([InlineKeyboardButton(text=label(item), callback_data=callback_data)])
    rows.extend(extra_rows or [])
    rows.append(nav_row_for_pages(prefix, page, last))
    rows.append([MENU_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# `page` and `size` are given; `edit` says whether to replace the current
# message or send a new one.
Renderer = Callable[[Message, int, int, bool], Awaitable[None]]


@dataclass(frozen=True)
class PagedView:
    """A registered list view, addressable by name from the goto-page prompt."""

    name: str
    size: int
    render: Renderer
    # Returns the total item count, so the goto prompt can reject out-of-range
    # input before rendering an empty page.
    count: Callable[[], Awaitable[int]]


_VIEWS: dict[str, PagedView] = {}


def register_view(view: PagedView) -> PagedView:
    """Make a view reachable from the shared goto-page handler."""
    _VIEWS[view.name] = view
    return view


def get_view(name: str | None) -> PagedView | None:
    return _VIEWS.get(name or "")


async def prompt_page_input(target: Message, state: FSMContext, *, view: PagedView) -> None:
    """Ask for a page number, remembering which view to render it in."""
    await state.update_data(page_view=view.name)
    await state.set_state(UserListPageState.page_input)
    await target.answer("Введите номер страницы:")


def parse_page(callback_data: str) -> int:
    """Trailing `:<n>` of a pagination callback; 1 when it isn't a number."""
    tail = callback_data.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() and int(tail) > 0 else 1

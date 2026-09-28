"""
Admin user management, split by flow.

This was one 1163-line module until Phase 2. The four list-based flows
(create/edit/delete/stats) each carried their own copy of the same pagination
machinery; that now lives in `app.handlers.admin.pagination`, and each flow
registers a `PagedView` so the shared "go to page N" prompt below can render
any of them without knowing which one it is.
"""

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers.admin.pagination import get_view, max_page
from app.handlers.admin.users import create, delete, edit, search, stats
from app.states.admin import UserListPageState

router = Router(name="admin_users")


@router.message(UserListPageState.page_input)
async def handle_page_input(message: Message, state: FSMContext):
    """Render the page number typed at any list view's goto prompt."""
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("❌ Введите номер страницы числом больше 0.")
        return

    data = await state.get_data()
    view = get_view(data.get("page_view"))
    if view is None:
        await message.answer("❌ Неизвестный тип списка. Попробуйте снова из меню.")
        await state.clear()
        return

    page = int(raw)
    try:
        last = max_page(await view.count(), view.size)
        if page > last:
            await message.answer(f"❌ Такой страницы нет. Доступно: 1..{last}.")
            return
        await view.render(message, page, view.size, False)
    except Exception as exc:
        await message.answer(f"❌ Ошибка: {exc}")
    finally:
        await state.clear()


for _module in (create, edit, delete, search, stats):
    router.include_router(_module.router)

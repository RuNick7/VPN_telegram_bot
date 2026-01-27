"""Quick host creation handlers."""

from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.services.access import check_admin_access
from app.services.hosts_manage import host_manage_service
from app.states.admin import HostQuickCreateState

router = Router(name="admin_hosts_quick")

INBOUNDS_PAGE_SIZE = 5
NODES_PAGE_SIZE = 5
SQUADS_PAGE_SIZE = 5


def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]]
    )


def _skip_tag_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin:host:tag:skip")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _paginate(items: List[Dict[str, Any]], page: int, size: int) -> tuple[List[Dict[str, Any]], int]:
    total_pages = max(1, (len(items) + size - 1) // size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * size
    return items[start : start + size], total_pages


def _page_controls(prefix: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    prev_page = max(1, page - 1)
    next_page = min(total_pages, page + 1)
    return [
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{next_page}"),
        ]
    ]


def _inbounds_keyboard(inbounds: List[Dict[str, Any]], page: int) -> InlineKeyboardMarkup:
    chunk, total_pages = _paginate(inbounds, page, INBOUNDS_PAGE_SIZE)
    rows = [
        [
            InlineKeyboardButton(
                text=f"{item.get('tag', 'inbound')}:{item.get('port', '-')}",
                callback_data=f"admin:host:inbound:{item.get('uuid')}",
            )
        ]
        for item in chunk
    ]
    rows.extend(_page_controls("admin:host:inbound:page", page, total_pages))
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _nodes_keyboard(nodes: List[Dict[str, Any]], selected: List[str], page: int) -> InlineKeyboardMarkup:
    chunk, total_pages = _paginate(nodes, page, NODES_PAGE_SIZE)
    rows = []
    for node in chunk:
        node_uuid = node.get("uuid")
        name = node.get("name", "node")
        is_selected = node_uuid in selected
        prefix = "✅" if is_selected else "⬜️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix} {name}",
                    callback_data=f"admin:host:nodes:toggle:{node_uuid}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="admin:host:nodes:done")])
    rows.extend(_page_controls("admin:host:nodes:page", page, total_pages))
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _squads_keyboard(squads: List[Dict[str, Any]], page: int) -> InlineKeyboardMarkup:
    chunk, total_pages = _paginate(squads, page, SQUADS_PAGE_SIZE)
    rows = [
        [
            InlineKeyboardButton(
                text=item.get("name", "squad"),
                callback_data=f"admin:host:squad:{item.get('uuid')}",
            )
        ]
        for item in chunk
    ]
    rows.extend(_page_controls("admin:host:squad:page", page, total_pages))
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _exclude_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="admin:host:exclude:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin:host:exclude:no"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


@router.callback_query(F.data == "admin:host_quick_add")
async def start_host_quick(callback: CallbackQuery, state: FSMContext):
    """Start quick host creation."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(HostQuickCreateState.remark)
    await callback.message.answer("Введите название хоста:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(HostQuickCreateState.remark)
async def handle_host_remark(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    remark = (message.text or "").strip()
    if not remark:
        await message.answer("❌ Название не может быть пустым.")
        return

    inbounds = await host_manage_service.list_inbounds()
    if not inbounds:
        await message.answer("❌ Inbound не найдены.", reply_markup=_menu_keyboard())
        await state.clear()
        return

    await state.update_data(remark=remark, inbounds=inbounds, inbound_page=1)
    await state.set_state(HostQuickCreateState.inbound)
    await message.answer("Выберите inbound:", reply_markup=_inbounds_keyboard(inbounds, 1))


@router.callback_query(F.data.startswith("admin:host:inbound:page:"))
async def host_inbound_page(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    data = await state.get_data()
    inbounds = data.get("inbounds", [])
    page = int(callback.data.split(":")[-1])
    await state.update_data(inbound_page=page)
    await callback.message.edit_reply_markup(reply_markup=_inbounds_keyboard(inbounds, page))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:inbound:"))
async def host_inbound_select(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    inbound_uuid = callback.data.split(":")[-1]
    data = await state.get_data()
    inbounds = data.get("inbounds", [])
    inbound = next((item for item in inbounds if item.get("uuid") == inbound_uuid), None)
    if not inbound:
        await callback.message.answer("❌ Не удалось найти inbound.", reply_markup=_menu_keyboard())
        await state.clear()
        await callback.answer()
        return

    await state.update_data(
        inbound={
            "configProfileUuid": inbound.get("profileUuid"),
            "configProfileInboundUuid": inbound.get("uuid"),
        }
    )
    await state.set_state(HostQuickCreateState.address)
    await callback.message.answer("Введите адрес (домен или IP):", reply_markup=_menu_keyboard())
    await callback.answer()


@router.message(HostQuickCreateState.address)
async def handle_host_address(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    address = (message.text or "").strip()
    if not address:
        await message.answer("❌ Адрес не может быть пустым.")
        return

    await state.update_data(address=address)
    await state.set_state(HostQuickCreateState.port)
    await message.answer("Введите порт:", reply_markup=_menu_keyboard())


@router.message(HostQuickCreateState.port)
async def handle_host_port(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Порт должен быть числом.")
        return

    await state.update_data(port=int(text))
    await state.set_state(HostQuickCreateState.tag)
    await message.answer("Введите тег (опционально):", reply_markup=_skip_tag_keyboard())


@router.callback_query(F.data == "admin:host:tag:skip")
async def handle_host_tag_skip(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        await state.clear()
        return

    nodes = await host_manage_service.list_nodes()
    await state.update_data(tag=None, nodes_all=nodes, nodes_selected=[], nodes_page=1)
    await state.set_state(HostQuickCreateState.nodes)
    await callback.message.answer("Выберите ноды:", reply_markup=_nodes_keyboard(nodes, [], 1))
    await callback.answer()


@router.message(HostQuickCreateState.tag)
async def handle_host_tag(message: Message, state: FSMContext):
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    tag = (message.text or "").strip()
    nodes = await host_manage_service.list_nodes()
    await state.update_data(tag=tag or None, nodes_all=nodes, nodes_selected=[], nodes_page=1)
    await state.set_state(HostQuickCreateState.nodes)
    await message.answer("Выберите ноды:", reply_markup=_nodes_keyboard(nodes, [], 1))


@router.callback_query(F.data.startswith("admin:host:nodes:page:"))
async def host_nodes_page(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    data = await state.get_data()
    nodes = data.get("nodes_all", [])
    selected = data.get("nodes_selected", [])
    page = int(callback.data.split(":")[-1])
    await state.update_data(nodes_page=page)
    await callback.message.edit_reply_markup(reply_markup=_nodes_keyboard(nodes, selected, page))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:nodes:toggle:"))
async def host_nodes_toggle(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    node_uuid = callback.data.split(":")[-1]
    data = await state.get_data()
    nodes = data.get("nodes_all", [])
    selected = set(data.get("nodes_selected", []))
    if node_uuid in selected:
        selected.remove(node_uuid)
    else:
        selected.add(node_uuid)
    selected_list = list(selected)
    page = data.get("nodes_page", 1)
    await state.update_data(nodes_selected=selected_list)
    await callback.message.edit_reply_markup(reply_markup=_nodes_keyboard(nodes, selected_list, page))
    await callback.answer()


@router.callback_query(F.data == "admin:host:nodes:done")
async def host_nodes_done(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    data = await state.get_data()
    selected = data.get("nodes_selected", [])
    if not selected:
        await callback.answer("Выберите хотя бы одну ноду.", show_alert=True)
        return

    squads = await host_manage_service.list_internal_squads()
    if not squads:
        await callback.message.answer("❌ Внутренние сквады не найдены.", reply_markup=_menu_keyboard())
        await state.clear()
        await callback.answer()
        return

    await state.update_data(squads_all=squads, squad_page=1)
    await state.set_state(HostQuickCreateState.squad)
    await callback.message.answer("Выберите внутренний сквад:", reply_markup=_squads_keyboard(squads, 1))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:squad:page:"))
async def host_squad_page(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    data = await state.get_data()
    squads = data.get("squads_all", [])
    page = int(callback.data.split(":")[-1])
    await state.update_data(squad_page=page)
    await callback.message.edit_reply_markup(reply_markup=_squads_keyboard(squads, page))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:squad:"))
async def host_squad_select(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    squad_uuid = callback.data.split(":")[-1]
    data = await state.get_data()
    squads = data.get("squads_all", [])
    excluded = [item.get("uuid") for item in squads if item.get("uuid") != squad_uuid]
    await state.update_data(selected_squad=squad_uuid, excluded_squads=excluded)
    await state.set_state(HostQuickCreateState.exclude_confirm)
    await callback.message.answer(
        "Исключить выбранный сквад из других хостов?",
        reply_markup=_exclude_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:exclude:"))
async def host_exclude_confirm(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    decision = callback.data.split(":")[-1]
    exclude_from_others = decision == "yes"

    data = await state.get_data()
    payload = {
        "inbound": data.get("inbound"),
        "remark": data.get("remark"),
        "address": data.get("address"),
        "port": data.get("port"),
        "nodes": data.get("nodes_selected", []),
        "excludedInternalSquads": data.get("excluded_squads", []),
        "isDisabled": False,
        "isHidden": False,
        "allowInsecure": False,
        "securityLayer": "DEFAULT",
    }
    if data.get("tag"):
        payload["tag"] = data.get("tag")

    try:
        host_response = await host_manage_service.create_host(payload)
        new_host_uuid = host_response.get("response", {}).get("uuid")

        updated = 0
        if exclude_from_others and new_host_uuid:
            hosts = await host_manage_service.list_hosts()
            for host in hosts:
                host_uuid = host.get("uuid")
                if not host_uuid or host_uuid == new_host_uuid:
                    continue
                detail = await host_manage_service.get_host(host_uuid)
                current = detail.get("excludedInternalSquads", []) or []
                if data.get("selected_squad") in current:
                    continue
                current.append(data.get("selected_squad"))
                await host_manage_service.update_host(
                    {"uuid": host_uuid, "excludedInternalSquads": current}
                )
                updated += 1

        await callback.message.answer(
            "✅ Хост создан.\n"
            f"Обновлено хостов: {updated}",
            reply_markup=_menu_keyboard(),
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
    finally:
        await state.clear()
        await callback.answer()

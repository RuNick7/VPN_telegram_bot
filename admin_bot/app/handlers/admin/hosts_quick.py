"""Quick host creation handlers."""

from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from app.handlers.admin.pagination import MENU_BUTTON, list_page_keyboard
from app.services.hosts_manage import host_manage_service
from app.states.admin import HostQuickCreateState

router = Router(name="admin_hosts_quick")

INBOUNDS_PAGE_SIZE = 5
NODES_PAGE_SIZE = 5
SQUADS_PAGE_SIZE = 5
HOSTS_PAGE_SIZE = 8


def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[MENU_BUTTON]])


def _skip_tag_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin:host:tag:skip")],
            [MENU_BUTTON],
        ]
    )


def _inbounds_keyboard(inbounds: List[Dict[str, Any]], page: int) -> InlineKeyboardMarkup:
    return list_page_keyboard(
        inbounds,
        page,
        INBOUNDS_PAGE_SIZE,
        prefix="admin:host:inbound:page",
        label=lambda item: f"{item.get('tag', 'inbound')}:{item.get('port', '-')}",
        item_callback=lambda item: f"admin:host:inbound:{item.get('uuid')}",
    )


def _multi_select_keyboard(
    items: List[Dict[str, Any]],
    selected: List[str],
    page: int,
    *,
    kind: str,
    size: int,
    default_name: str,
) -> InlineKeyboardMarkup:
    """
    Checkbox list with a Done button -- used for both nodes and squads, which
    differ only in callback namespace and the fallback label.
    """
    return list_page_keyboard(
        items,
        page,
        size,
        prefix=f"admin:host:{kind}:page",
        label=lambda item: (
            f"{'✅' if item.get('uuid') in selected else '⬜️'} {item.get('name', default_name)}"
        ),
        item_callback=lambda item: (
            f"admin:host:{kind}:toggle:{item['uuid']}" if item.get("uuid") else None
        ),
        extra_rows=[
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"admin:host:{kind}:done")]
        ],
    )


def _nodes_keyboard(nodes: List[Dict[str, Any]], selected: List[str], page: int) -> InlineKeyboardMarkup:
    return _multi_select_keyboard(
        nodes, selected, page, kind="nodes", size=NODES_PAGE_SIZE, default_name="node"
    )


def _squads_keyboard(squads: List[Dict[str, Any]], selected: List[str], page: int) -> InlineKeyboardMarkup:
    return _multi_select_keyboard(
        squads, selected, page, kind="squads", size=SQUADS_PAGE_SIZE, default_name="squad"
    )


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

def _hosts_delete_keyboard(hosts: List[Dict[str, Any]], page: int) -> InlineKeyboardMarkup:
    return list_page_keyboard(
        hosts,
        page,
        HOSTS_PAGE_SIZE,
        prefix="admin:host:del:page",
        label=lambda item: (
            f"{item.get('remark') or item.get('address', 'host')}:{item.get('port', '-')}"
        ),
        item_callback=lambda item: (
            f"admin:host:del:uuid:{item['uuid']}" if item.get("uuid") else None
        ),
    )


@router.callback_query(F.data == "admin:host_quick_add")
async def start_host_quick(callback: CallbackQuery, state: FSMContext):
    """Start quick host creation."""
    await state.clear()
    await state.set_state(HostQuickCreateState.remark)
    await callback.message.answer("Введите название хоста:", reply_markup=_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:host_delete")
async def start_host_delete(callback: CallbackQuery, state: FSMContext):
    """Start host delete flow."""
    await state.clear()
    try:
        hosts = await host_manage_service.list_hosts()
        if not hosts:
            await callback.message.answer("📭 Хосты не найдены.", reply_markup=_menu_keyboard())
            await callback.answer()
            return
        await callback.message.answer(
            "Выберите хост для удаления:",
            reply_markup=_hosts_delete_keyboard(hosts, 1),
        )
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
        await callback.answer()


@router.callback_query(F.data.startswith("admin:host:del:page:"))
async def host_delete_page(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split(":")[-1])
        hosts = await host_manage_service.list_hosts()
        total_pages = max(1, (len(hosts) + HOSTS_PAGE_SIZE - 1) // HOSTS_PAGE_SIZE)
        page = max(1, min(page, total_pages))
        try:
            await callback.message.edit_reply_markup(reply_markup=_hosts_delete_keyboard(hosts, page))
        except TelegramBadRequest as e:
            if "message is not modified" not in (str(e) or ""):
                raise
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
        await callback.answer()


@router.callback_query(F.data.startswith("admin:host:del:uuid:"))
async def host_delete_select(callback: CallbackQuery, state: FSMContext):
    host_uuid = callback.data.split(":")[-1]
    try:
        await host_manage_service.delete_host(host_uuid)
        await callback.message.answer("✅ Хост удален.", reply_markup=_menu_keyboard())
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}", reply_markup=_menu_keyboard())
        await callback.answer()


@router.message(HostQuickCreateState.remark)
async def handle_host_remark(message: Message, state: FSMContext):
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
    data = await state.get_data()
    inbounds = data.get("inbounds", [])
    total_pages = max(1, (len(inbounds) + INBOUNDS_PAGE_SIZE - 1) // INBOUNDS_PAGE_SIZE)
    page = max(1, min(int(callback.data.split(":")[-1]), total_pages))
    await state.update_data(inbound_page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=_inbounds_keyboard(inbounds, page))
    except TelegramBadRequest as e:
        if "message is not modified" not in (str(e) or ""):
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:inbound:"))
async def host_inbound_select(callback: CallbackQuery, state: FSMContext):
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
    address = (message.text or "").strip()
    if not address:
        await message.answer("❌ Адрес не может быть пустым.")
        return

    await state.update_data(address=address)
    await state.set_state(HostQuickCreateState.port)
    await message.answer("Введите порт:", reply_markup=_menu_keyboard())


@router.message(HostQuickCreateState.port)
async def handle_host_port(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Порт должен быть числом.")
        return

    await state.update_data(port=int(text))
    await state.set_state(HostQuickCreateState.tag)
    await message.answer("Введите тег (опционально):", reply_markup=_skip_tag_keyboard())


@router.callback_query(F.data == "admin:host:tag:skip")
async def handle_host_tag_skip(callback: CallbackQuery, state: FSMContext):
    nodes = await host_manage_service.list_nodes()
    await state.update_data(tag=None, nodes_all=nodes, nodes_selected=[], nodes_page=1)
    await state.set_state(HostQuickCreateState.nodes)
    await callback.message.answer("Выберите ноды:", reply_markup=_nodes_keyboard(nodes, [], 1))
    await callback.answer()


@router.message(HostQuickCreateState.tag)
async def handle_host_tag(message: Message, state: FSMContext):
    tag = (message.text or "").strip()
    nodes = await host_manage_service.list_nodes()
    await state.update_data(tag=tag or None, nodes_all=nodes, nodes_selected=[], nodes_page=1)
    await state.set_state(HostQuickCreateState.nodes)
    await message.answer("Выберите ноды:", reply_markup=_nodes_keyboard(nodes, [], 1))


@router.callback_query(F.data.startswith("admin:host:nodes:page:"))
async def host_nodes_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    nodes = data.get("nodes_all", [])
    selected = data.get("nodes_selected", [])
    total_pages = max(1, (len(nodes) + NODES_PAGE_SIZE - 1) // NODES_PAGE_SIZE)
    page = max(1, min(int(callback.data.split(":")[-1]), total_pages))
    await state.update_data(nodes_page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=_nodes_keyboard(nodes, selected, page))
    except TelegramBadRequest as e:
        if "message is not modified" not in (str(e) or ""):
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:nodes:toggle:"))
async def host_nodes_toggle(callback: CallbackQuery, state: FSMContext):
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
    try:
        await callback.message.edit_reply_markup(reply_markup=_nodes_keyboard(nodes, selected_list, page))
    except TelegramBadRequest as e:
        if "message is not modified" not in (str(e) or ""):
            raise
    await callback.answer()


@router.callback_query(F.data == "admin:host:nodes:done")
async def host_nodes_done(callback: CallbackQuery, state: FSMContext):
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

    await state.update_data(squads_all=squads, squads_selected=[], squad_page=1)
    await state.set_state(HostQuickCreateState.squad)
    await callback.message.answer(
        "Выберите внутренние сквады (можно несколько):",
        reply_markup=_squads_keyboard(squads, [], 1),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:squads:page:"))
async def host_squad_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    squads = data.get("squads_all", [])
    selected = data.get("squads_selected", [])
    total_pages = max(1, (len(squads) + SQUADS_PAGE_SIZE - 1) // SQUADS_PAGE_SIZE)
    page = max(1, min(int(callback.data.split(":")[-1]), total_pages))
    await state.update_data(squad_page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=_squads_keyboard(squads, selected, page))
    except TelegramBadRequest as e:
        if "message is not modified" not in (str(e) or ""):
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:squads:toggle:"))
async def host_squad_toggle(callback: CallbackQuery, state: FSMContext):
    squad_uuid = callback.data.split(":")[-1]
    data = await state.get_data()
    squads = data.get("squads_all", [])
    selected = set(data.get("squads_selected", []))
    if squad_uuid in selected:
        selected.remove(squad_uuid)
    else:
        selected.add(squad_uuid)
    selected_list = list(selected)
    page = data.get("squad_page", 1)
    await state.update_data(squads_selected=selected_list)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=_squads_keyboard(squads, selected_list, page)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in (str(e) or ""):
            raise
    await callback.answer()


@router.callback_query(F.data == "admin:host:squads:done")
async def host_squads_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    squads = data.get("squads_all", [])
    selected_squads = data.get("squads_selected", [])
    if not selected_squads:
        await callback.answer("Выберите хотя бы один сквад.", show_alert=True)
        return

    all_squad_uuids = [item.get("uuid") for item in squads if item.get("uuid")]
    excluded = [squad_uuid for squad_uuid in all_squad_uuids if squad_uuid not in selected_squads]
    await state.update_data(selected_squads=selected_squads, excluded_squads=excluded)
    await state.set_state(HostQuickCreateState.exclude_confirm)
    await callback.message.answer(
        "Исключить выбранные сквады из других хостов?",
        reply_markup=_exclude_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:host:exclude:"))
async def host_exclude_confirm(callback: CallbackQuery, state: FSMContext):
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
                selected_squads = data.get("selected_squads", [])
                updated_current = list(current)
                changed = False
                for squad_uuid in selected_squads:
                    if squad_uuid and squad_uuid not in updated_current:
                        updated_current.append(squad_uuid)
                        changed = True
                if not changed:
                    continue
                await host_manage_service.update_host(
                    {"uuid": host_uuid, "excludedInternalSquads": updated_current}
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

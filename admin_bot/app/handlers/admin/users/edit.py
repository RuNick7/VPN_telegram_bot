"""Edit an existing panel user's fields."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from tgvpn_shared.db import LteRepository
from tgvpn_shared.remnawave.client import panel_ref
from tgvpn_shared.settings import get_settings

from app.handlers.admin.pagination import (
    PagedView,
    parse_page,
    picker_keyboard,
    prompt_page_input,
    register_view,
)
from app.handlers.admin.users.common import (
    HANDLE_PROMPT,
    DATE_FOREVER,
    account_label,
    count_accounts,
    fetch_accounts_page,
    edit_again_keyboard,
    edit_expire_keyboard,
    edit_field_keyboard,
    edit_start_keyboard,
    expire_at_of,
    parse_iso_datetime,
    find_db_row,
    find_panel_user,
    telegram_id_of,
    users_repo,
)
from app.services.users import user_service
from app.states.admin import UserEditState

router = Router(name="admin_users_edit")

lte_repo = LteRepository()

PREFIX = "admin:edit_user:list"
GOTO = "admin:edit_user:list:goto"
PAGE_SIZE = 10

BYTES_PER_GB = 1024**3


async def render(target: Message, page: int, size: int, edit: bool) -> None:
    users, total = await fetch_accounts_page(page, size)
    if not users:
        await target.answer("📭 Пользователи не найдены.")
        return
    keyboard = picker_keyboard(
        users,
        label=account_label,
        item_callback=lambda user: f"admin:edit_user:select_id:{user['id']}",
        prefix=PREFIX,
        page=page,
        total=total,
        size=size,
        goto_callback_data=GOTO,
    )
    if edit:
        await target.edit_text("Выберите пользователя:", reply_markup=keyboard)
    else:
        await target.answer("Выберите пользователя:", reply_markup=keyboard)


VIEW = register_view(PagedView(name="edit", size=PAGE_SIZE, render=render, count=count_accounts))


async def _open_field_menu(target: Message, state: FSMContext, user: dict, username: str) -> None:
    """Remember which user is being edited and offer the field picker."""
    telegram_id = telegram_id_of(user, username)
    # Our own row id, resolved once here. It is the only handle a website
    # account has, and every field we store rather than the panel -- the
    # address, the referrer, the invite count, both LTE quotas -- is addressed
    # by it. Resolving it once means none of them has to ask again.
    row = await find_db_row(username) or (
        await find_db_row(str(telegram_id)) if telegram_id else None
    )
    await state.update_data(
        user_uuid=panel_ref(user) or None,
        username=username,
        telegram_id=telegram_id,
        row_id=str(row["id"]) if row else None,
        expire_at=expire_at_of(user),
    )
    await state.set_state(UserEditState.field)
    await target.answer(
        f"Пользователь: {username}\nВыберите поле для редактирования:",
        reply_markup=edit_field_keyboard(),
    )


async def _open_db_only_menu(target: Message, state: FSMContext, row: dict) -> None:
    """
    The field picker for an account with no panel profile.

    Same menu; what differs is that `user_uuid` is empty, so `apply_update`
    refuses the panel-side fields instead of sending them nowhere.
    """
    await state.update_data(
        user_uuid=None,
        username=row.get("remnawave_username") or str(row["id"])[:8],
        telegram_id=row.get("telegram_id"),
        row_id=str(row["id"]),
        expire_at=None,
    )
    await state.set_state(UserEditState.field)
    await target.answer(
        f"Пользователь: {account_label(row)}\nВыберите поле для редактирования:",
        reply_markup=edit_field_keyboard(),
    )


async def apply_update(
    message: Message,
    state: FSMContext,
    payload: dict,
    new_telegram_id: int | None = None,
) -> None:
    """
    Push one field change to the panel, mirroring it into our database.

    Expiry and telegram_id are the two fields we also store, so they are
    written through to the subscription row; everything else is panel-only.

    The mirror is not optional for expiry. `subscription_expire_monitor`
    decides who is expired from *our* column, not from the panel -- so a
    change that reached Remnawave alone is undone by the next monitor pass,
    which reads the old date and demotes the user to the free squad. That is
    what happened to every website account: the write was keyed on
    telegram_id, which they do not have.
    """
    data = await state.get_data()
    user_uuid = data.get("user_uuid")
    telegram_id = data.get("telegram_id")
    row_id = data.get("row_id")
    if not user_uuid:
        # Either nothing was picked, or the account has no panel profile --
        # which the list can now show, so the message has to tell the two
        # apart instead of claiming nobody was selected.
        await message.answer(
            "❌ У этого аккаунта нет профиля в Remnawave — менять срок, лимит "
            "и tag не в чем.\nПочта, пригласивший и квоты трафика доступны."
            if row_id
            else "❌ Не выбран пользователь."
        )
        if not row_id:
            await state.clear()
        return

    mirrored = True
    try:
        await user_service.update_user(user_uuid, payload)

        if "expire_at" in payload:
            ends = int(payload["expire_at"].timestamp())
            if telegram_id:
                await users_repo.upsert_subscription_expire(
                    telegram_id=telegram_id, subscription_ends=ends
                )
            elif row_id:
                await users_repo.set_subscription_expire_by_user_id(row_id, ends)
            else:
                # No row of ours at all: a panel account nothing else knows
                # about. Said out loud rather than left to be discovered when
                # the site shows a different date.
                mirrored = False
        if new_telegram_id and telegram_id:
            expire_at = data.get("expire_at")
            parsed = parse_iso_datetime(expire_at) if isinstance(expire_at, str) else None
            await users_repo.upsert_subscription_telegram_id(
                old_telegram_id=telegram_id,
                new_telegram_id=new_telegram_id,
                subscription_ends=int(parsed.timestamp()) if parsed else None,
            )
            await state.update_data(telegram_id=new_telegram_id)

        # Says where it landed. "Обновлен" alone left an operator with no way
        # to tell a change that reached both systems from one that reached
        # only the panel and would be reverted by the next monitor pass.
        text = (
            "✅ Обновлено в Remnawave и в базе."
            if mirrored
            else "⚠️ Обновлено только в Remnawave.\n"
            "У этого аккаунта нет записи в нашей базе, поэтому срок на сайте "
            "и в боте не изменится."
        )
        await message.answer(text, reply_markup=edit_again_keyboard())
        await state.set_state(UserEditState.field)
    except Exception as exc:
        await message.answer(f"❌ Ошибка при обновлении: {exc}")
        await state.clear()


# -- entry points ----------------------------------------------------------


@router.callback_query(F.data == "admin:edit_user")
async def start_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Выберите способ поиска пользователя:", reply_markup=edit_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:edit_user:username")
async def prompt_username(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserEditState.username)
    await callback.message.answer(HANDLE_PROMPT)
    await callback.answer()


@router.callback_query(F.data == PREFIX)
async def show_list(callback: CallbackQuery):
    try:
        await render(callback.message, 1, PAGE_SIZE, edit=False)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data == GOTO)
async def goto_prompt(callback: CallbackQuery, state: FSMContext):
    await prompt_page_input(callback.message, state, view=VIEW)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{PREFIX}:"))
async def show_page(callback: CallbackQuery):
    try:
        await render(callback.message, parse_page(callback.data), PAGE_SIZE, edit=True)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:select_id:"))
async def select_account_from_list(callback: CallbackQuery, state: FSMContext):
    """
    Open the edit menu for a row picked out of our own list.

    The panel account is resolved from the row rather than the other way
    round, so an account whose profile is missing still opens -- its
    database-only fields are editable and the panel-side ones report the
    profile is not there, which beats the account being unlistable.
    """
    row_id = callback.data.rsplit(":", 1)[-1]
    try:
        row = await users_repo.get_user_by_uuid(row_id)
        if row is None:
            await callback.message.answer("❌ Запись не найдена — возможно, аккаунт уже удалён.")
            await callback.answer()
            return

        row = dict(row)
        user, name = await find_panel_user(row.get("remnawave_username") or row_id, row)
        if not user:
            await callback.message.answer(
                "⚠️ У этого аккаунта нет профиля в Remnawave.\n"
                "Поля панели (срок, лимит, tag) редактировать нечем — "
                "остальные доступны."
            )
            await _open_db_only_menu(callback.message, state, row)
        else:
            await _open_field_menu(callback.message, state, user, str(name))
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:select_uuid:"))
async def select_from_list(callback: CallbackQuery, state: FSMContext):
    """Kept for buttons in messages sent before the list moved to our own rows."""
    user_uuid = callback.data.rsplit(":", 1)[-1]
    try:
        user = await user_service.get_user_by_uuid(user_uuid)
        username = user.get("username")
        if not username:
            await callback.message.answer("❌ Не удалось получить пользователя.")
        else:
            await _open_field_menu(callback.message, state, user, str(username))
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
    await callback.answer()


@router.message(UserEditState.username)
async def select_by_username(message: Message, state: FSMContext):
    """
    Open the edit menu for whoever the admin named.

    Any handle: a Telegram ID, an email, a @tag, our UUID, or the panel
    username. It used to accept the panel username alone, which an admin
    rarely has and a website account is not named after.
    """
    needle = (message.text or "").strip()
    try:
        row = await find_db_row(needle)
        user, name = await find_panel_user(needle, row)
        if not user:
            await message.answer(
                "❌ Аккаунт в Remnawave не найден."
                + ("\nℹ️ В базе запись есть — панельный профиль удалён или ещё не создан."
                   if row else "")
            )
            return
        await _open_field_menu(message, state, user, name)
    except Exception as exc:
        await message.answer(f"❌ Ошибка: {exc}")


# -- field selection and values -------------------------------------------


@router.callback_query(F.data.startswith("admin:edit_user:field:"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.rsplit(":", 1)[-1]
    await state.update_data(field=field)
    await state.set_state(UserEditState.value)

    prompts = {
        "traffic_limit_bytes": "Введите лимит трафика в ГБ (например 1 или 1.5):",
        "hwid_device_limit": "Введите лимит устройств HWID:",
        "referrer_tag": (
            "Введите @ник пригласившего (или <code>-</code>, чтобы очистить).\n\n"
            "Бонус пригласившему начислится при следующей оплате этого пользователя."
        ),
        "email": (
            "Введите новый email (или <code>-</code>, чтобы удалить).\n\n"
            "Это способ входа на сайт: после смены ссылка для входа будет "
            "приходить на новый адрес, а по старому войти уже нельзя."
        ),
    }
    if field == "expire_at":
        await callback.message.answer(
            "Выберите новый срок действия:", reply_markup=edit_expire_keyboard()
        )
    elif field == "referred_people":
        await callback.message.answer(
            await _referred_people_prompt(await state.get_data()), parse_mode="HTML"
        )
    elif field in ("lte_free_gb", "lte_balance_gb"):
        await callback.message.answer(
            await _lte_prompt(await state.get_data(), field), parse_mode="HTML"
        )
    else:
        await callback.message.answer(prompts.get(field, "Введите новое значение:"))
    await callback.answer()


async def _referred_people_prompt(data: dict) -> str:
    """
    Ask for a new invite count, showing what it currently is and what it buys.

    The count isn't decoration: it picks the user's price tier, so an admin
    setting it is really granting a discount and should see which one.
    """
    current = "?"
    row_id = data.get("row_id")
    if row_id:
        row = await users_repo.get_user_by_uuid(row_id)
        if row is not None:
            current = int(row["referred_people"] or 0)

    return (
        f"Приглашённых сейчас: <b>{current}</b>\n"
        f"(скидочный тариф считается от этого числа, максимум на {MAX_DISCOUNT_TIER})\n\n"
        "Введите новое значение:\n"
        "• <code>5</code> — установить ровно 5\n"
        "• <code>+3</code> — добавить 3\n"
        "• <code>-2</code> — убавить 2"
    )


async def _lte_prompt(data: dict, field: str) -> str:
    """Ask for an LTE value, showing what it is now and what it controls."""
    row_id = data.get("row_id")
    state = await lte_repo.get_state_by_user_id(row_id) if row_id else None

    if field == "lte_free_gb":
        override = state.get("lte_free_gb_override") if state else None
        current = (
            f"{override} ГБ (персонально)"
            if override is not None
            else f"{get_settings().lte_free_gb_per_cycle} ГБ (общая настройка)"
        )
        return (
            f"Бесплатных ГБ в месяц сейчас: <b>{current}</b>\n\n"
            "Введите число ГБ для этого пользователя,\n"
            "или <code>-</code> чтобы вернуть общую настройку.\n\n"
            "<i>0 — это тоже значение: значит без бесплатного трафика.</i>"
        )

    balance = int(state["lte_paid_balance_bytes"] or 0) if state else 0
    return (
        f"Купленный трафик белых списков сейчас: <b>{balance / 1024**3:.2f} ГБ</b>\n\n"
        "Введите, сколько ГБ начислить:\n"
        "• <code>+10</code> — добавить 10 ГБ\n"
        "• <code>0</code> — обнулить баланс\n\n"
        "<i>Купленный трафик переходит на следующий месяц.</i>"
    )


@router.callback_query(F.data == "admin:edit_user:back")
async def back_to_field_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("user_uuid"):
        await callback.message.answer(
            "Выберите способ поиска пользователя:", reply_markup=edit_start_keyboard()
        )
        await state.set_state(UserEditState.username)
    else:
        await callback.message.answer(
            f"Пользователь: {data.get('username', 'unknown')}\nВыберите поле для редактирования:",
            reply_markup=edit_field_keyboard(),
        )
        await state.set_state(UserEditState.field)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_user:expire:"))
async def choose_expire_preset(callback: CallbackQuery, state: FSMContext):
    action = callback.data.rsplit(":", 1)[-1]
    presets = {
        "forever": DATE_FOREVER,
        "month": datetime.now(timezone.utc) + timedelta(days=30),
        "week": datetime.now(timezone.utc) + timedelta(days=7),
    }
    if action in presets:
        await apply_update(callback.message, state, {"expire_at": presets[action]})
    else:
        await callback.message.answer("Введите количество дней до окончания:")
    await callback.answer()


@router.message(UserEditState.value)
async def receive_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    text = (message.text or "").strip()

    if field == "traffic_limit_bytes":
        try:
            gigabytes = float(text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число в ГБ (например 1 или 1.5).")
            return
        await apply_update(message, state, {"traffic_limit_bytes": int(gigabytes * BYTES_PER_GB)})
        return

    if field == "hwid_device_limit":
        if not text.isdigit():
            await message.answer("❌ Введите числовой лимит устройств.")
            return
        await apply_update(message, state, {"hwidDeviceLimit": int(text)})
        return

    if field == "expire_at":
        if not text.isdigit():
            await message.answer("❌ Введите количество дней числом.")
            return
        await apply_update(
            message, state, {"expire_at": datetime.now(timezone.utc) + timedelta(days=int(text))}
        )
        return

    if field == "tag":
        await apply_update(message, state, {"tag": text})
        return

    if field in DB_ONLY_FIELDS:
        await _apply_db_only_update(message, state, field, text)
        return

    await message.answer("❌ Неизвестное поле.")


# Fields that live only in our database -- the panel has no concept of them, so
# these skip `apply_update` (which would send them to Remnawave) entirely.
DB_ONLY_FIELDS = {"referrer_tag", "referred_people", "lte_free_gb", "lte_balance_gb", "email"}

# Deliberately loose: anything stricter rejects real addresses, and what
# actually decides whether an address works is whether mail reaches it.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

# Typed instead of a nickname to clear the referrer.
CLEAR_TOKENS = {"-", "—", "none", "нет", "очистить"}

# The row was there when the edit menu opened and is not there now -- deleted
# under us, or merged into another account.
NO_ROW = "❌ Запись в базе не найдена — возможно, аккаунт удалён или объединён."

# `get_subscription_price` caps the discount tier at this many referrals, so
# setting a higher number buys nothing extra. Kept here rather than imported
# because it lives in user_bot, which admin_bot cannot import.
MAX_DISCOUNT_TIER = 5


def parse_count_input(text: str) -> tuple[int, bool] | None:
    """
    Parse `5`, `+3`, or `-2` into `(value, is_relative)`.

    Relative input exists because "he invited 3 more" is the common edit, and
    doing it as a delta means the admin doesn't have to read the current value
    and do the arithmetic themselves.
    """
    text = text.strip().replace(" ", "")
    if not text:
        return None
    relative = text[0] in "+-"
    digits = text[1:] if relative else text
    if not digits.isdigit():
        return None
    value = int(digits)
    return (-value if text[0] == "-" else value), relative


async def _apply_email_update(message: Message, data: dict, text: str) -> None:
    """
    Change or clear the address an account signs in with.

    Refused when somebody else holds it rather than moved: the address is a
    way into an account, and reassigning one would take that way off whoever
    has it. Clearing is allowed, but only for an account that has another
    identity -- otherwise it would be left with no route in at all.
    """
    row_id = data.get("row_id")
    if not row_id:
        await message.answer(
            "❌ У этого аккаунта нет записи в нашей базе — почту хранить негде."
        )
        return

    if text.lower() in CLEAR_TOKENS:
        if not data.get("telegram_id"):
            await message.answer(
                "❌ Нельзя удалить почту: это единственный способ войти в аккаунт. "
                "Сначала привяжите Telegram."
            )
            return
        await users_repo.admin_set_email(row_id, None)
        await message.answer("✅ Почта удалена.", reply_markup=edit_again_keyboard())
        return

    email = text.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        await message.answer("❌ Похоже, это не email. Введите адрес или <code>-</code>.",
                             parse_mode="HTML")
        return

    existing = await users_repo.get_user_by_email(email)
    if existing and str(existing["id"]) != str(row_id):
        await message.answer("❌ Этот адрес уже привязан к другому аккаунту.")
        return

    await users_repo.admin_set_email(row_id, email)
    await message.answer(f"✅ Почта: {email}", reply_markup=edit_again_keyboard())


async def _apply_db_only_update(
    message: Message, state: FSMContext, field: str, text: str
) -> None:
    """
    Write a database-only field, addressed by our own id.

    Every one of these used to be keyed on telegram_id, which meant they were
    unusable for exactly the accounts the website creates: the row existed, the
    column existed, and the edit reported "нет telegram_id" and did nothing.
    `id` is the identity (see `shared/tgvpn_shared/identity.py`) and every
    account has one, so that is what these address.

    An account with no row of ours at all -- a panel profile nothing else knows
    about -- is still reported rather than silently skipped.
    """
    data = await state.get_data()
    row_id = data.get("row_id")

    if field == "email":
        await _apply_email_update(message, data, text)
        return

    if not row_id:
        await message.answer(
            "❌ У этого аккаунта нет записи в нашей базе — эти поля хранятся "
            "только у нас, поэтому менять нечего."
        )
        return

    try:
        if field == "referrer_tag":
            tag = None if text.lower() in CLEAR_TOKENS else text.lstrip("@").strip()
            if tag == "":
                await message.answer("❌ Введите @ник или <code>-</code> для очистки.")
                return
            if not await users_repo.admin_set_referrer_by_user_id(row_id, tag):
                await message.answer(NO_ROW)
                return
            result = f"пригласивший: @{tag}" if tag else "пригласивший очищен"
        elif field == "lte_free_gb":
            # `-` clears the override; 0 is a real value meaning no free traffic.
            gigabytes = None if text.lower() in CLEAR_TOKENS else text
            if gigabytes is not None and not gigabytes.isdigit():
                await message.answer("❌ Введите число ГБ или <code>-</code> для общей настройки.")
                return
            if not await lte_repo.set_free_gb_override_by_user_id(
                row_id, None if gigabytes is None else int(gigabytes)
            ):
                await message.answer(NO_ROW)
                return
            result = (
                f"бесплатно {gigabytes} ГБ/мес"
                if gigabytes is not None
                else f"бесплатные ГБ по общей настройке ({get_settings().lte_free_gb_per_cycle})"
            )

        elif field == "lte_balance_gb":
            parsed = parse_count_input(text)
            if parsed is None:
                await message.answer(
                    "❌ Введите число ГБ: <code>+10</code> чтобы начислить, <code>0</code> чтобы обнулить."
                )
                return
            value, relative = parsed
            if relative:
                new_bytes = await lte_repo.credit_balance_by_user_id(row_id, value * 1024**3)
            else:
                new_bytes = await lte_repo.set_balance_by_user_id(row_id, value * 1024**3)
            if new_bytes is None:
                await message.answer(NO_ROW)
                return
            result = f"трафик белых списков: {new_bytes / 1024**3:.2f} ГБ"

        else:
            parsed = parse_count_input(text)
            if parsed is None:
                await message.answer(
                    "❌ Введите число: <code>5</code>, <code>+3</code> или <code>-2</code>."
                )
                return
            value, relative = parsed
            if relative:
                new_count = await users_repo.adjust_referred_people_by_user_id(row_id, value)
            else:
                new_count = await users_repo.set_referred_people_by_user_id(row_id, value)

            if new_count is None:
                await message.answer(NO_ROW)
                return
            tier = min(new_count, MAX_DISCOUNT_TIER)
            result = f"приглашено: {new_count} (скидочный тариф {tier}/{MAX_DISCOUNT_TIER})"

        await message.answer(f"✅ Обновлено — {result}.", reply_markup=edit_again_keyboard())
        await state.set_state(UserEditState.field)
    except Exception as exc:
        await message.answer(f"❌ Ошибка при обновлении: {exc}")
        await state.clear()

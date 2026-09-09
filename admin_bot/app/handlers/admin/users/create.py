"""
Create a panel user through a step-by-step form.

Each optional step offers a Skip button, so every step has a message handler
(value typed) and a callback handler (skipped) that both advance to the same
next step. `_advance` owns that shared "move to step N" behaviour so the two
entry points can't drift apart.
"""

from __future__ import annotations

import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from app.handlers.admin.users.common import (
    DATE_FOREVER,
    create_expire_keyboard,
    skip_keyboard,
    users_repo,
)
from app.services.users import user_service
from app.states.admin import UserCreateState

router = Router(name="admin_users_create")

# What a panel account may be called.
#
# Two shapes, because the project has two. Accounts created before the identity
# rework are named after the Telegram ID; everything created since is named
# `u-<16 hex>` by `identity.panel_username_for`, and a website account has no
# Telegram ID to be named after at all. Accepting only the first meant the
# admin bot could not create the kind of account the website makes.
USERNAME_RE = re.compile(r"^(?:\d{6,20}|u-[0-9a-f]{6,32})$")
# Deliberately loose: anything stricter rejects real addresses, and the point
# here is to catch a typed-in name rather than to validate a mailbox.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


async def _advance(target: Message, state: FSMContext, step: State, prompt: str, skip: str) -> None:
    await state.set_state(step)
    await target.answer(prompt, reply_markup=skip_keyboard(skip))


async def _ask_tag(target: Message, state: FSMContext) -> None:
    await _advance(target, state, UserCreateState.tag, "Введите tag (или пропустите):", "tag")


async def _ask_telegram_id(target: Message, state: FSMContext) -> None:
    await _advance(
        target,
        state,
        UserCreateState.telegram_id,
        "Введите telegram_id (или пропустите):",
        "telegram_id",
    )


async def _ask_email(target: Message, state: FSMContext) -> None:
    await _advance(
        target,
        state,
        UserCreateState.email,
        "Введите email (или пропустите).\n"
        "С ним пользователь сможет войти в кабинет на сайте — без него только через бота:",
        "email",
    )


async def _ask_hwid(target: Message, state: FSMContext) -> None:
    await _advance(
        target,
        state,
        UserCreateState.hwid_device_limit,
        "Введите лимит устройств HWID (или пропустите):",
        "hwid",
    )


@router.callback_query(F.data == "admin:new_user")
async def start_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserCreateState.username)
    await callback.message.answer(
        "Введите username для нового пользователя.\n\n"
        "• только цифры (Telegram ID), от 6 знаков — как у аккаунтов из бота\n"
        "• или <code>u-</code> и 6–32 hex-символа — как у аккаунтов с сайта",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(UserCreateState.username)
async def receive_username(message: Message, state: FSMContext):
    username = (message.text or "").strip().lower()
    if not USERNAME_RE.fullmatch(username):
        await message.answer(
            "❌ Некорректный username.\n"
            "Нужны либо цифры (Telegram ID, от 6 знаков), либо <code>u-</code> и 6–32 hex-символа.",
            parse_mode="HTML",
        )
        return
    await state.update_data(username=username)
    await state.set_state(UserCreateState.expire_at)
    await message.answer(
        "Выберите срок действия пользователя:", reply_markup=create_expire_keyboard()
    )


@router.callback_query(F.data.startswith("admin:new_user:expire:"))
async def receive_expire(callback: CallbackQuery, state: FSMContext):
    action = callback.data.rsplit(":", 1)[-1]
    presets = {
        "forever": DATE_FOREVER,
        "month": datetime.now(timezone.utc) + timedelta(days=30),
        "week": datetime.now(timezone.utc) + timedelta(days=7),
    }
    # Skipping still needs *some* expiry -- the panel requires one -- so a
    # skipped step means "one day", the most conservative default.
    await state.update_data(
        expire_at=presets.get(action, datetime.now(timezone.utc) + timedelta(days=1))
    )
    # Straight to the tag: this form no longer asks for Remnawave's own traffic
    # limit. Nothing in the project reads it, our per-cycle quota is what
    # enforces traffic, and an account created with a panel limit is one the
    # panel can cut off early for a reason no screen here would explain -- the
    # edit menu deliberately can't set it either. Left unsent, the panel
    # defaults to unlimited, which is the state the quota assumes.
    await _ask_tag(callback.message, state)
    await callback.answer()


@router.message(UserCreateState.tag)
async def receive_tag(message: Message, state: FSMContext):
    tag = (message.text or "").strip()
    if tag:
        await state.update_data(tag=tag)
    await _ask_telegram_id(message, state)


@router.callback_query(F.data == "admin:new_user:skip:tag")
async def skip_tag(callback: CallbackQuery, state: FSMContext):
    await _ask_telegram_id(callback.message, state)
    await callback.answer()


@router.message(UserCreateState.telegram_id)
async def receive_telegram_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой telegram_id или нажмите Пропустить.")
        return
    await state.update_data(telegram_id=int(text))
    await _ask_email(message, state)


@router.callback_query(F.data == "admin:new_user:skip:telegram_id")
async def skip_telegram_id(callback: CallbackQuery, state: FSMContext):
    await _ask_email(callback.message, state)
    await callback.answer()


@router.message(UserCreateState.email)
async def receive_email(message: Message, state: FSMContext):
    email = (message.text or "").strip().lower()
    if not EMAIL_RE.fullmatch(email):
        await message.answer("❌ Похоже, это не email. Введите адрес или нажмите Пропустить.")
        return
    # Refused rather than overwritten: the address is a sign-in route, and
    # moving one onto a new account would take it off whoever holds it.
    if await users_repo.get_user_by_email(email):
        await message.answer("❌ Этот email уже занят другим аккаунтом. Введите другой или пропустите.")
        return
    await state.update_data(email=email)
    await _ask_hwid(message, state)


@router.callback_query(F.data == "admin:new_user:skip:email")
async def skip_email(callback: CallbackQuery, state: FSMContext):
    await _ask_hwid(callback.message, state)
    await callback.answer()


@router.message(UserCreateState.hwid_device_limit)
async def receive_hwid(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой лимит устройств или нажмите Пропустить.")
        return
    await state.update_data(hwid_device_limit=int(text))
    await _finalize(message, state)


@router.callback_query(F.data == "admin:new_user:skip:hwid")
async def skip_hwid(callback: CallbackQuery, state: FSMContext):
    await _finalize(callback.message, state)
    await callback.answer()


async def _finalize(message: Message, state: FSMContext) -> None:
    """Create the user from everything collected, then reset the form."""
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    email = data.get("email")

    # A skipped Telegram ID used to fall back to the *sender's* -- so an admin
    # creating an account for somebody else, and skipping the step because they
    # did not know it, attached that account to their own. With an email there
    # is now a real alternative identity; with neither, the account exists in
    # the panel alone and the reply says so rather than guessing.
    if not telegram_id and not email:
        # Derive the numeric case from the username, which for a bot-style name
        # *is* the Telegram ID. Nothing is guessed for a `u-...` name.
        if str(data.get("username", "")).isdigit():
            telegram_id = int(data["username"])

    try:
        user = await user_service.create_user(
            username=data["username"],
            expire_at=data.get("expire_at"),
            tag=data.get("tag"),
            telegram_id=telegram_id,
            hwid_device_limit=data.get("hwid_device_limit"),
            email=email,
        )
        identity = (
            f"\nTelegram ID: {telegram_id}" if telegram_id else ""
        ) + (f"\nEmail: {email}" if email else "")
        if not identity:
            identity = "\n⚠️ Ни telegram_id, ни email — аккаунт есть только в панели."
        await message.answer(
            "✅ Пользователь создан.\n"
            f"Username: {user.get('username')}\n"
            f"UUID: {user.get('uuid')}\n"
            f"Sub URL: {user.get('subscription_url') or user.get('subscriptionUrl')}"
            + identity
        )
    except socket.gaierror:
        await message.answer(
            "❌ Ошибка DNS: не удалось разрешить адрес панели.\n"
            "Проверь `REMNAWAVE_BASE_URL` и доступность хоста."
        )
    except httpx.RequestError as exc:
        if "nodename nor servname" in str(exc).lower():
            host = urlparse(user_service.client.base_url).hostname or user_service.client.base_url
            await message.answer(
                "❌ Ошибка DNS при подключении к панели.\n"
                f"Хост: {host}\n"
                "Проверь `REMNAWAVE_BASE_URL`, DNS и доступность хоста."
            )
        else:
            await message.answer(f"❌ Ошибка сети: {exc}")
    except Exception as exc:
        await message.answer(f"❌ Ошибка при создании пользователя: {exc}")
    finally:
        await state.clear()

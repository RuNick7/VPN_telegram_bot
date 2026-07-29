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
)
from app.services.users import user_service
from app.states.admin import UserCreateState

router = Router(name="admin_users_create")

# Panel usernames for bot-created accounts are the Telegram ID itself.
USERNAME_RE = re.compile(r"^\d{6,20}$")
BYTES_PER_GB = 1024**3


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
        "Введите username для нового пользователя.\n"
        "Требования: только цифры (Telegram ID), минимум 6 символов."
    )
    await callback.answer()


@router.message(UserCreateState.username)
async def receive_username(message: Message, state: FSMContext):
    username = (message.text or "").strip()
    if not USERNAME_RE.fullmatch(username):
        await message.answer(
            "❌ Некорректный username. Нужны только цифры (Telegram ID), минимум 6 символов."
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
    await _advance(
        callback.message,
        state,
        UserCreateState.traffic_limit_bytes,
        "Введите лимит трафика в ГБ (например: 1 или 1.5):",
        "traffic",
    )
    await callback.answer()


@router.message(UserCreateState.traffic_limit_bytes)
async def receive_traffic(message: Message, state: FSMContext):
    try:
        gigabytes = float((message.text or "").strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число в ГБ (например 1 или 1.5) или нажмите Пропустить.")
        return
    await state.update_data(traffic_limit_bytes=int(gigabytes * BYTES_PER_GB))
    await _ask_tag(message, state)


@router.callback_query(F.data == "admin:new_user:skip:traffic")
async def skip_traffic(callback: CallbackQuery, state: FSMContext):
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
    await _ask_hwid(message, state)


@router.callback_query(F.data == "admin:new_user:skip:telegram_id")
async def skip_telegram_id(callback: CallbackQuery, state: FSMContext):
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
    try:
        user = await user_service.create_user(
            username=data["username"],
            expire_at=data.get("expire_at"),
            traffic_limit_bytes=data.get("traffic_limit_bytes"),
            tag=data.get("tag"),
            # No telegram_id given means the admin is creating an account for
            # themselves, which is the only sensible default here.
            telegram_id=data.get("telegram_id") or message.from_user.id,
            hwid_device_limit=data.get("hwid_device_limit"),
        )
        await message.answer(
            "✅ Пользователь создан.\n"
            f"Username: {user.get('username')}\n"
            f"UUID: {user.get('uuid')}\n"
            f"Sub URL: {user.get('subscription_url') or user.get('subscriptionUrl')}"
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

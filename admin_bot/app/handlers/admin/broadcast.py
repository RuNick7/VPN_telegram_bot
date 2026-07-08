"""Admin broadcast handlers."""

import asyncio
import io
import logging
from urllib.parse import urlparse

from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.input_file import BufferedInputFile
from aiogram.fsm.context import FSMContext

from app.config.settings import settings
from app.services.access import check_admin_access
from app.services.subscription_db import get_all_telegram_ids
from app.states.admin import BroadcastState

router = Router(name="admin_broadcast")
logger = logging.getLogger(__name__)

BATCH_SIZE = 25
PAUSE_BETWEEN_BATCHES = 1.0  # seconds
PAUSE_BETWEEN_MESSAGES = 0.05
MAX_FAIL_REPORT = 10  # сколько ошибок показать админу в сообщении
MAX_BROADCAST_BUTTONS = 6

# Эти callback_data должны обрабатываться user_bot.
ALLOWED_USER_BOT_MENU_CALLBACKS: dict[str, str] = {
    "main_menu": "☰ Главное меню",
    "subscription_tariffs": "💳 Продлить подписку",
    "referral_info": "👥 Реферальная программа",
    "help": "❓ Помощь",
    "os:android": "🤖 Android",
    "os:ios": "🍎 iPhone",
    "os:windows": "🪟 Windows",
    "os:macos": "🍏 macOS",
    "os:linux": "🐧 Linux",
    "os:tv": "📺 Android-TV",
    "os:appletv": "🍏 Apple TV",
}

def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")]]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Запустить", callback_data="admin:broadcast:send"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast:cancel"),
            ],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:menu")],
        ]
    )


def _buttons_prompt_text() -> str:
    menu_lines = "\n".join(
        [f"• {title} -> `{cb}`" for cb, title in ALLOWED_USER_BOT_MENU_CALLBACKS.items()]
    )
    return (
        "Теперь настройте кнопки рассылки (необязательно).\n\n"
        "Отправьте `-` чтобы без кнопок.\n"
        f"Или до {MAX_BROADCAST_BUTTONS} строк в формате:\n"
        "`Текст кнопки | menu | callback_data`\n"
        "`Текст кнопки | url | https://example.com`\n\n"
        "Доступные menu callback_data:\n"
        f"{menu_lines}"
    )


def _validate_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _parse_broadcast_buttons(raw_text: str) -> tuple[list[dict], str | None]:
    text = (raw_text or "").strip()
    if text == "-":
        return [], None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [], "❌ Пустой ввод. Отправьте `-` или строки с кнопками."
    if len(lines) > MAX_BROADCAST_BUTTONS:
        return [], f"❌ Слишком много кнопок. Максимум: {MAX_BROADCAST_BUTTONS}."

    buttons: list[dict] = []
    for i, line in enumerate(lines, start=1):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            return [], (
                f"❌ Ошибка в строке {i}. Нужен формат:\n"
                "`Текст кнопки | menu | callback_data`\n"
                "или\n"
                "`Текст кнопки | url | https://example.com`"
            )
        label, btn_type, value = parts
        if not label:
            return [], f"❌ Строка {i}: пустой текст кнопки."
        if len(label) > 64:
            return [], f"❌ Строка {i}: текст кнопки слишком длинный (макс. 64)."
        if btn_type not in ("menu", "url"):
            return [], f"❌ Строка {i}: тип должен быть `menu` или `url`."

        if btn_type == "menu":
            if value not in ALLOWED_USER_BOT_MENU_CALLBACKS:
                return [], (
                    f"❌ Строка {i}: callback_data `{value}` не разрешён.\n"
                    "Используйте только значения из списка."
                )
            buttons.append({"text": label, "type": "menu", "value": value})
            continue

        if not _validate_url(value):
            return [], f"❌ Строка {i}: некорректный URL `{value}`."
        buttons.append({"text": label, "type": "url", "value": value})

    return buttons, None


def _build_broadcast_reply_markup(buttons: list[dict] | None) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for item in buttons:
        if item.get("type") == "url":
            rows.append([InlineKeyboardButton(text=item["text"], url=item["value"])])
        else:
            rows.append([InlineKeyboardButton(text=item["text"], callback_data=item["value"])])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast flow."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(BroadcastState.content)
    await callback.message.answer(
        "Отправьте сообщение для рассылки.\n"
        "Можно текст или фото/видео с подписью.",
        reply_markup=_menu_keyboard(),
    )
    await callback.answer()


@router.message(BroadcastState.content)
async def capture_broadcast_content(message: Message, state: FSMContext):
    """Capture broadcast content (text/photo/video)."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption or ""
        await state.update_data(kind="photo", file_id=file_id, caption=caption)
        await state.set_state(BroadcastState.buttons)
        await message.answer(_buttons_prompt_text(), reply_markup=_menu_keyboard())
        return

    if message.video:
        file_id = message.video.file_id
        caption = message.caption or ""
        await state.update_data(kind="video", file_id=file_id, caption=caption)
        await state.set_state(BroadcastState.buttons)
        await message.answer(_buttons_prompt_text(), reply_markup=_menu_keyboard())
        return

    if message.text:
        await state.update_data(kind="text", text=message.text)
        await state.set_state(BroadcastState.buttons)
        await message.answer(_buttons_prompt_text(), reply_markup=_menu_keyboard())
        return

    await message.answer("❌ Отправьте текст или фото/видео с подписью.")


@router.message(BroadcastState.buttons)
async def capture_broadcast_buttons(message: Message, state: FSMContext):
    """Capture and validate broadcast buttons."""
    if not await check_admin_access(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    if not message.text:
        await message.answer("❌ Отправьте текст с кнопками или `-`.")
        return

    buttons, error = _parse_broadcast_buttons(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(buttons=buttons)
    await state.set_state(BroadcastState.confirm)
    if buttons:
        preview = "\n".join([f"• {b['text']} ({b['type']}: {b['value']})" for b in buttons])
        text = f"Готово. Кнопки настроены:\n{preview}\n\nЗапустить рассылку?"
    else:
        text = "Готово. Рассылка будет без кнопок.\n\nЗапустить рассылку?"
    await message.answer(text, reply_markup=_confirm_keyboard())


@router.callback_query(F.data == "admin:broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast."""
    await state.clear()
    await callback.message.answer("Рассылка отменена.", reply_markup=_menu_keyboard())
    await callback.answer()


def _short_reason(exc: Exception) -> str:
    """Краткое описание ошибки для отчёта админу."""
    s = str(exc).strip()
    if "blocked" in s.lower() or "deactivated" in s.lower():
        return "заблокировал бота"
    if "chat not found" in s.lower() or "user not found" in s.lower():
        return "чат не найден"
    if "bot can't initiate" in s.lower() or "have no rights" in s.lower():
        return "пользователь не начинал диалог с ботом"
    if len(s) > 60:
        return s[:57] + "..."
    return s or type(exc).__name__


@router.callback_query(F.data == "admin:broadcast:send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Send broadcast to all telegram_id from DB. Uses user_bot token if set (пользователи общаются с user_bot)."""
    if not await check_admin_access(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return
    # Acknowledge callback immediately to avoid "query is too old" on long broadcasts.
    await callback.answer("⏳ Запускаю рассылку...")

    data = await state.get_data()
    kind = data.get("kind")
    ids = await get_all_telegram_ids()

    if not ids:
        await callback.message.answer("❌ В базе нет пользователей.", reply_markup=_menu_keyboard())
        await state.clear()
        return

    use_user_bot = bool(settings.user_bot_token and settings.user_bot_token.strip())
    admin_bot = callback.bot
    if use_user_bot:
        send_bot = Bot(token=settings.user_bot_token.strip())
        try:
            await _do_broadcast(callback, state, data, kind, ids, send_bot, admin_bot, from_user_bot=True)
        finally:
            await send_bot.session.close()
    else:
        logger.warning(
            "USER_BOT_TOKEN не задан: рассылка идёт от админ-бота. "
            "Доставка только тем, кто начинал диалог с админ-ботом. Задайте USER_BOT_TOKEN в .env."
        )
        await _do_broadcast(callback, state, data, kind, ids, admin_bot, admin_bot, from_user_bot=False)


async def _do_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    data: dict,
    kind: str,
    ids: list[int],
    send_bot: Bot,
    admin_bot: Bot,
    *,
    from_user_bot: bool,
) -> None:
    sent = 0
    failed_list: list[tuple[int, str]] = []
    reply_markup = _build_broadcast_reply_markup(data.get("buttons"))

    photo_file: BufferedInputFile | None = None
    video_file: BufferedInputFile | None = None
    use_user_bot_for_media = send_bot is not admin_bot and kind in ("photo", "video")
    if use_user_bot_for_media:
        file_id = data.get("file_id")
        if file_id:
            try:
                bio = await admin_bot.download(file_id)
                if bio and isinstance(bio, io.BytesIO):
                    bio.seek(0)
                    inp = BufferedInputFile(bio.read(), filename="broadcast.jpg" if kind == "photo" else "broadcast.mp4")
                    if kind == "photo":
                        photo_file = inp
                    else:
                        video_file = inp
            except Exception as e:
                logger.exception("Не удалось скачать файл рассылки с админ-бота: %s", e)
                await callback.message.answer(
                    "❌ Не удалось подготовить медиа для рассылки (скачать файл).",
                    reply_markup=_menu_keyboard(),
                )
                return

    # После первой успешной загрузки байтов медиа переключаемся на file_id
    # этого сообщения: иначе одно и то же видео заливается в Telegram заново
    # для каждого получателя.
    media_file_id: str | None = data.get("file_id") if not use_user_bot_for_media else None

    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        for tg_id in batch:
            try:
                if kind == "text":
                    await send_bot.send_message(tg_id, data.get("text", ""), reply_markup=reply_markup)
                elif kind == "photo":
                    if media_file_id is None and photo_file is not None:
                        sent_msg = await send_bot.send_photo(
                            tg_id,
                            photo_file,
                            caption=data.get("caption"),
                            reply_markup=reply_markup,
                        )
                        if sent_msg.photo:
                            media_file_id = sent_msg.photo[-1].file_id
                    else:
                        await send_bot.send_photo(
                            tg_id,
                            media_file_id or data.get("file_id"),
                            caption=data.get("caption"),
                            reply_markup=reply_markup,
                        )
                elif kind == "video":
                    if media_file_id is None and video_file is not None:
                        sent_msg = await send_bot.send_video(
                            tg_id,
                            video_file,
                            caption=data.get("caption"),
                            reply_markup=reply_markup,
                        )
                        if sent_msg.video:
                            media_file_id = sent_msg.video.file_id
                    else:
                        await send_bot.send_video(
                            tg_id,
                            media_file_id or data.get("file_id"),
                            caption=data.get("caption"),
                            reply_markup=reply_markup,
                        )
                else:
                    failed_list.append((tg_id, "неизвестный тип рассылки"))
                    continue
                sent += 1
                await asyncio.sleep(PAUSE_BETWEEN_MESSAGES)
            except Exception as e:
                reason = _short_reason(e)
                failed_list.append((tg_id, reason))
                logger.warning("Рассылка tg_id=%s: %s", tg_id, e, exc_info=False)
        await asyncio.sleep(PAUSE_BETWEEN_BATCHES)

    failed = len(failed_list)
    report_lines = [
        f"✅ Рассылка завершена.",
        f"Отправлено от: {'user_bot' if from_user_bot else 'админ-бот'}",
        f"Доставлено: {sent}",
        f"Ошибки: {failed}",
    ]
    if failed_list:
        for tg_id, reason in failed_list[:MAX_FAIL_REPORT]:
            report_lines.append(f"  • {tg_id}: {reason}")
        if failed > MAX_FAIL_REPORT:
            report_lines.append(f"  … и ещё {failed - MAX_FAIL_REPORT} (см. лог)")

    await callback.message.answer("\n".join(report_lines), reply_markup=_menu_keyboard())
    await state.clear()

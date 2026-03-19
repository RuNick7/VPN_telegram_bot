import time

from aiogram import BaseMiddleware
from aiogram.types import Message

from data.db_utils import get_user_by_id
from handlers.email_state import EmailCaptureState


class EmailGateMiddleware(BaseMiddleware):
    """
    Ask for email on any command after 1 day from registration.
    Users with saved email pass through without restrictions.
    """

    EMAIL_DELAY_SECONDS = 86_400

    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)

        text = (event.text or "").strip()
        if not text.startswith("/"):
            return await handler(event, data)

        state = data.get("state")
        if state and await state.get_state() == EmailCaptureState.waiting_email.state:
            await event.answer(
                "✉️ Сначала укажите email в формате example@mail.com, "
                "после этого команды снова будут доступны."
            )
            return

        user = get_user_by_id(event.from_user.id)
        if not user:
            return await handler(event, data)

        email = ""
        if "email" in user.keys():
            email = (user["email"] or "").strip()

        if email:
            return await handler(event, data)

        created_at_raw = user["created_at"] if "created_at" in user.keys() else 0
        try:
            created_at = int(created_at_raw or 0)
        except (TypeError, ValueError):
            created_at = 0

        # For brand-new users we allow normal flow; ask after 1 day.
        if created_at and int(time.time()) - created_at < self.EMAIL_DELAY_SECONDS:
            return await handler(event, data)

        if state:
            await state.set_state(EmailCaptureState.waiting_email)

        await event.answer(
            "✉️ Пожалуйста, укажите ваш email.\n\n"
            "Он нужен, чтобы в будущем вы могли зайти на сайт и управлять подпиской "
            "даже при полной блокировке Telegram.\n"
            "Пример: example@mail.com"
        )
        return

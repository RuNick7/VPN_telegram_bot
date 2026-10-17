"""
Asking a customer to check the servers with the vpncheck program.

The ask is an answer in the ticket, written on the operator's behalf, so it
reaches the customer wherever answers do: in user_bot when they have
Telegram, and in the cabinet either way. The program does the rest: the
customer pastes their subscription link, and «Отправить в поддержку» puts
the report into their open ticket. Pressing it is the consent; nothing is
collected before.
"""

from __future__ import annotations


def check_request_text(download_url: str) -> str:
    """The answer the customer gets, as plain text: it is stored as a ticket message."""
    return (
        "Чтобы понять, почему не работает VPN, проверьте серверы с компьютера:\n"
        f"1. Скачайте программу «KairaVPN Проверка» для Windows, macOS или Linux: {download_url}\n"
        "2. Выключите VPN-приложение (Happ и другие).\n"
        "3. Запустите программу, вставьте ссылку на подписку и нажмите «Проверить».\n"
        "4. Нажмите «Отправить в поддержку» — отчёт придёт в это обращение. "
        "Можно и «Скопировать файл», чтобы прислать его в чат поддержки в Telegram.\n\n"
        "Из отчёта вырезаются ключи, ссылка на подписку и ваш IP-адрес. "
        "На Mac при первом запуске откройте Системные настройки → Конфиденциальность и безопасность "
        "и нажмите «Всё равно открыть»."
    )

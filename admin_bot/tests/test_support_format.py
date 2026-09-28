"""
How a support ticket reads in the operators' chat.

Two things here are not cosmetic. The admin bot parses every message as HTML,
so a customer's `<` has to arrive escaped or it breaks the card -- or formats
it. And Telegram refuses a message past 4096 characters counted in UTF-16, so
a long message, or one full of emoji, has to be cut by that measure or it is
refused on every pass for good.
"""

import re
import time
from html import unescape

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramServerError,
)
from aiogram.methods import SendMessage

from app.services.support import (
    card_messages,
    chat_unreachable,
    clean_name,
    customer_notice,
    follow_up_messages,
    format_size,
    history_messages,
    refused,
    split_text,
    subscription_line,
    utf16_len,
    who,
)

NOW = int(time.time())
METHOD = SendMessage(chat_id=1, text="x")


def visible(html_text: str) -> str:
    """What Telegram counts: the text after tags and entities are parsed."""
    return unescape(re.sub(r"<[^>]+>", "", html_text))


def message(**kwargs) -> dict:
    base = dict(
        id=10,
        ticket_id=7,
        subject="Не подключается",
        body="Пишет ошибку",
        opens_ticket=True,
        user_id="0f8f6b1e-0000-4000-8000-000000000000",
        email="customer@example.com",
        telegram_id=None,
        telegram_tag="",
        subscription_ends=NOW + 3 * 86400,
        attachments=[],
    )
    return {**base, **kwargs}


# -- escaping -------------------------------------------------------------------


def test_the_customers_words_cannot_become_markup():
    [card] = card_messages(
        message(subject="<b>срочно</b>", body="<script>alert(1)</script> & <a href=x>", email="a&b@example.com"),
        NOW,
    )
    assert "<script>" not in card
    assert "&lt;script&gt;" in card
    assert "&lt;b&gt;срочно&lt;/b&gt;" in card
    assert "a&amp;b@example.com" in card


def test_a_card_says_who_is_asking_and_how_to_answer():
    [card] = card_messages(message(telegram_id=555, telegram_tag="nick"), NOW)
    assert "Обращение #7" in card
    assert "customer@example.com · @nick · tg <code>555</code>" in card
    assert "осталось 3 дн." in card
    assert "Ответьте на это сообщение" in card


def test_a_customer_with_no_subscription_is_said_to_have_none():
    assert subscription_line(NOW - 86400, NOW) == "нет активной подписки"
    assert subscription_line(None, NOW) == "нет активной подписки"


def test_somebody_with_no_handles_at_all_is_not_a_blank():
    assert who({"email": None, "telegram_tag": "", "telegram_id": None}) == "без контактов"


def test_a_card_mentions_the_files_that_follow_it():
    [card] = card_messages(message(attachments=[{"id": "a"}, {"id": "b"}]), NOW)
    assert "Файлов: 2" in card


def test_a_message_with_only_files_says_so_rather_than_nothing():
    [card] = card_messages(message(body=""), NOW)
    assert "(без текста)" in card
    [follow_up] = follow_up_messages(message(body="", opens_ticket=False))
    assert "только файлы" in follow_up


# -- length ---------------------------------------------------------------------


def test_a_long_message_is_cut_into_parts_telegram_accepts():
    body = "\n".join(f"Строка {i}: " + "подробности " * 8 for i in range(200))
    parts = card_messages(message(body=body), NOW)
    assert len(parts) > 1
    for part in parts:
        assert utf16_len(visible(part)) <= 4096
    # Nothing lost on the way.
    rejoined = " ".join(visible(p) for p in parts)
    assert "Строка 199" in rejoined


def test_emoji_are_counted_the_way_telegram_counts_them():
    # Each of these is two UTF-16 units. Cut by Python's own length, the
    # first part would be twice what Telegram allows.
    body = "😀" * 4000
    parts = split_text(body)
    assert all(utf16_len(part) <= 3900 for part in parts)
    assert "".join(parts) == body


def test_text_is_cut_at_a_line_break_when_there_is_one():
    text = "а" * 2000 + "\n" + "б" * 2000
    first, second = split_text(text, 3000, 3000)
    assert first == "а" * 2000
    assert second == "б" * 2000


def test_a_single_endless_word_is_still_cut():
    parts = split_text("x" * 7000, 3000, 3000)
    assert [len(p) for p in parts] == [3000, 3000, 1000]


def test_the_history_is_packed_under_the_limit():
    thread = [
        {"author": "user" if i % 2 else "admin", "body": "текст " * 300, "created_at": NOW, "attachments": []}
        for i in range(12)
    ]
    parts = history_messages({"id": 7, "subject": "Тема", "status": "open"}, thread)
    assert len(parts) > 1
    assert all(utf16_len(visible(part)) <= 4096 for part in parts)


def test_a_purged_file_is_named_as_such_in_the_history():
    thread = [
        {
            "author": "user", "body": "", "created_at": NOW,
            "attachments": [{"file_name": "clip.mov", "size_bytes": 5 * 1024 * 1024, "purged": True}],
        }
    ]
    [text] = history_messages({"id": 7, "subject": "Тема", "status": "closed"}, thread)
    assert "clip.mov (5,0 МБ) — удалён по сроку" in text


# -- the customer's side -----------------------------------------------------------


def test_the_customer_is_told_what_was_answered_and_where_to_continue():
    text = customer_notice(
        7, "Оплата <не прошла>",
        [{"body": "Деньги вернулись", "attachment_count": 1}, {"body": "", "attachment_count": 2}],
        with_link=True,
    )
    assert "обращение #7" in text
    assert "«Оплата &lt;не прошла&gt;»" in text
    assert "Деньги вернулись" in text
    assert "Файлов в ответе: 3" in text


def test_a_long_answer_is_shortened_in_the_notice_not_refused():
    text = customer_notice(7, "Тема", [{"body": "слово " * 2000, "attachment_count": 0}], with_link=False)
    assert utf16_len(visible(text)) < 4096
    assert "…" in text
    assert "на сайте" in text


# -- small things ---------------------------------------------------------------------


def test_file_names_from_telegram_lose_their_path_and_stay_short():
    assert clean_name("../../etc/passwd", "file") == "passwd"
    assert clean_name(r"C:\docs\отчёт.pdf", "file") == "отчёт.pdf"
    assert clean_name(None, "photo_1.jpg") == "photo_1.jpg"
    long = clean_name("я" * 300 + ".mp4", "file")
    assert len(long) == 100 and long.endswith(".mp4")


def test_sizes():
    assert format_size(2048) == "2 КБ"
    assert format_size(3 * 1024 * 1024 // 2) == "1,5 МБ"
    assert format_size(44 * 1024 * 1024) == "44 МБ"


# -- which failures are worth retrying -------------------------------------------------


def test_a_blocked_or_missing_chat_is_skipped_not_retried():
    assert chat_unreachable(TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user"))
    assert chat_unreachable(TelegramBadRequest(METHOD, "Bad Request: chat not found"))
    assert not refused(TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user"))


def test_a_file_too_large_is_refused_for_good_not_a_network_blip():
    # TelegramEntityTooLarge derives from TelegramNetworkError. Treated as a
    # blip, it would be retried forever and hold up every ticket behind it.
    too_large = TelegramEntityTooLarge(METHOD, "Request Entity Too Large")
    assert isinstance(too_large, TelegramNetworkError)
    assert refused(too_large)


def test_temporary_failures_are_neither():
    for exc in (
        TelegramNetworkError(METHOD, "timeout"),
        TelegramServerError(METHOD, "Bad Gateway"),
        ConnectionResetError("reset"),
    ):
        assert not refused(exc)
        assert not chat_unreachable(exc)


def test_a_bad_request_about_the_content_is_refused():
    assert refused(TelegramBadRequest(METHOD, "Bad Request: PHOTO_INVALID_DIMENSIONS"))

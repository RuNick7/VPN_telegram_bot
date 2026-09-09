"""
Legal documents in the bot.

A payment service has to be able to produce the agreement on demand. The
property worth guarding is that an unconfigured URL is *named as missing*
rather than rendered as a button that 404s — a customer looking for the terms
should learn they are not published yet, not be sent to a dead page and
conclude there aren't any.
"""

import pytest
from tgvpn_shared.settings import get_settings

from handlers.documents import (
    DOCUMENTS,
    available_documents,
    documents_keyboard,
    documents_text,
    missing_documents,
)
from handlers.keyboards import help_menu_keyboard

ALL_URLS = {
    "license_url": "https://example.com/license",
    "privacy_policy_url": "https://example.com/privacy",
}


@pytest.fixture
def docs(monkeypatch):
    """Every document configured."""
    settings = get_settings()
    for field, url in ALL_URLS.items():
        monkeypatch.setattr(settings, field, url)
    return settings


@pytest.fixture
def no_docs(monkeypatch):
    settings = get_settings()
    for field in ALL_URLS:
        monkeypatch.setattr(settings, field, "")
    return settings


def _buttons(keyboard):
    return [button for row in keyboard.inline_keyboard for button in row]


# -- the two we publish ----------------------------------------------------


def test_both_documents_are_offered(docs):
    titles = " ".join(document.title for document, _url in available_documents())
    assert "Лицензионное соглашение" in titles
    assert "Политика конфиденциальности" in titles


def test_every_configured_document_becomes_a_link(docs):
    links = [b for b in _buttons(documents_keyboard()) if b.url]
    assert len(links) == len(DOCUMENTS)
    assert {b.url for b in links} == set(ALL_URLS.values())


def test_there_is_always_a_way_back(docs):
    assert any(b.callback_data == "main_menu" for b in _buttons(documents_keyboard()))


# -- missing ones ----------------------------------------------------------


def test_an_unconfigured_document_gets_no_button(monkeypatch, docs):
    monkeypatch.setattr(get_settings(), "privacy_policy_url", "")

    links = [b for b in _buttons(documents_keyboard()) if b.url]
    assert len(links) == len(DOCUMENTS) - 1
    assert "https://example.com/privacy" not in {b.url for b in links}


def test_a_missing_document_is_named_rather_than_hidden(monkeypatch, docs):
    """Silence would read as "there is no privacy policy"."""
    monkeypatch.setattr(get_settings(), "privacy_policy_url", "")

    text = documents_text()
    assert "не опубликован" in text
    assert "конфиденциальности" in text


def test_nothing_configured_says_so_and_points_at_support(no_docs):
    text = documents_text()
    assert "не опубликован" in text
    assert "поддержку" in text
    assert not [b for b in _buttons(documents_keyboard()) if b.url]


def test_no_missing_notice_when_everything_is_published(docs):
    assert "не опубликован" not in documents_text()
    assert missing_documents() == []


# -- reachability ----------------------------------------------------------


def test_the_help_menu_links_to_the_documents():
    """`/docs` is only discoverable if you already know it exists."""
    assert any(b.callback_data == "documents" for b in _buttons(help_menu_keyboard()))

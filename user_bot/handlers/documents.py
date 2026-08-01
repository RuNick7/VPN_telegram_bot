"""
Legal documents: the offer, the refund policy, the terms of use.

A payment service has to be able to show these on demand, and "somewhere on
the site" is not good enough when the customer is standing in a Telegram chat
about to pay. `/docs` puts them one command away, and the same list is linked
from the help menu.

Every URL comes from configuration. An unset one is reported as not yet
published rather than rendered as a dead button -- a legal document that 404s
is worse than one that is honestly missing.
"""

from dataclasses import dataclass

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgvpn_shared.settings import get_settings

router = Router()


@dataclass(frozen=True)
class Document:
    title: str
    # Name of the settings field holding the URL.
    setting: str


DOCUMENTS: tuple[Document, ...] = (
    Document("📄 Публичная оферта", "offer_url"),
    Document("↩️ Политика возвратов", "refund_policy_url"),
    Document("📜 Пользовательское соглашение", "terms_url"),
    Document("🔒 Политика конфиденциальности", "privacy_policy_url"),
)


def available_documents() -> list[tuple[Document, str]]:
    """The documents that actually have a URL configured, with it."""
    settings = get_settings()
    found = []
    for document in DOCUMENTS:
        url = str(getattr(settings, document.setting, "") or "").strip()
        if url:
            found.append((document, url))
    return found


def missing_documents() -> list[Document]:
    configured = {document for document, _url in available_documents()}
    return [document for document in DOCUMENTS if document not in configured]


def documents_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=document.title, url=url)]
        for document, url in available_documents()
    ]
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def documents_text() -> str:
    available = available_documents()
    if not available:
        return (
            "📄 <b>Документы</b>\n\n"
            "Документы пока не опубликованы. Напишите в поддержку — пришлём."
        )

    text = "📄 <b>Документы</b>\n\nОткройте нужный документ по кнопке ниже."
    missing = missing_documents()
    if missing:
        # Named rather than silently omitted: a customer looking for the
        # refund policy should learn it is not published yet, not conclude
        # there isn't one.
        names = ", ".join(document.title.split(" ", 1)[1].lower() for document in missing)
        text += f"\n\nПока не опубликованы: {names}. Напишите в поддержку — пришлём."
    return text


async def send_documents(target: types.Message | types.CallbackQuery) -> None:
    if isinstance(target, types.CallbackQuery):
        await target.answer()
        await target.message.answer(
            documents_text(), parse_mode="HTML", reply_markup=documents_keyboard()
        )
        return
    await target.answer(documents_text(), parse_mode="HTML", reply_markup=documents_keyboard())


@router.message(Command("docs"))
async def documents_cmd(message: types.Message) -> None:
    await send_documents(message)


@router.callback_query(F.data == "documents")
async def documents_cb(cb: types.CallbackQuery) -> None:
    await send_documents(cb)

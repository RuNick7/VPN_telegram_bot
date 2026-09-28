"""
`/promo` as a one-line command versus the two-step prompt.

`/promo` alone used to be the only form: it always answered "enter the
code" and moved to `PromoState.waiting_for_promo`, discarding anything a
user typed after the command on the same line. `/promo CODE` now redeems
immediately, through the same `_redeem_promo_code` helper the prompted flow
calls -- so the two entry points can never validate or credit a code
differently from each other.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.referrals as referrals

TELEGRAM_ID = 555

DAYS_PROMO = {
    "code": "SUMMER30",
    "is_active": True,
    "type": "days",
    "value": 30,
}


def command(args: str | None) -> SimpleNamespace:
    return SimpleNamespace(args=args)


class FakeMessage:
    def __init__(self, text: str = "", user_id: int = TELEGRAM_ID):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.sent: list[dict] = []

    async def answer(self, text, **kwargs):
        self.sent.append({"text": text, **kwargs})
        return SimpleNamespace()

    @property
    def last(self) -> str:
        return self.sent[-1]["text"]


class FakeState:
    def __init__(self):
        self.set_state = AsyncMock()
        self.clear = AsyncMock()


@pytest.fixture
def promo(monkeypatch):
    fake = SimpleNamespace(
        get_promo_by_code=AsyncMock(return_value=dict(DAYS_PROMO)),
        try_claim_promo_usage=AsyncMock(return_value=True),
        release_promo_usage=AsyncMock(),
    )
    monkeypatch.setattr(referrals, "_promo", fake)
    monkeypatch.setattr(
        referrals, "_extend_subscription_async", AsyncMock(return_value="ok")
    )
    return fake


# -- `/promo` alone: unchanged two-step prompt ------------------------------


async def test_promo_with_no_code_still_prompts_and_waits(promo):
    message = FakeMessage()
    state = FakeState()

    await referrals.promo_code_entry(message, state, command(None))

    assert "Введите промокод" in message.last
    state.set_state.assert_awaited_once_with(referrals.PromoState.waiting_for_promo)
    state.clear.assert_not_awaited()
    promo.get_promo_by_code.assert_not_awaited()


async def test_promo_with_only_whitespace_after_it_also_prompts(promo):
    """`/promo ` (trailing space, nothing else) is not a code."""
    message = FakeMessage()
    state = FakeState()

    await referrals.promo_code_entry(message, state, command("   "))

    assert "Введите промокод" in message.last
    promo.get_promo_by_code.assert_not_awaited()


# -- `/promo CODE`: redeems inline -------------------------------------------


async def test_promo_with_inline_code_redeems_immediately(promo):
    message = FakeMessage()
    state = FakeState()

    await referrals.promo_code_entry(message, state, command("summer30"))

    promo.get_promo_by_code.assert_awaited_once_with("SUMMER30")
    promo.try_claim_promo_usage.assert_awaited_once()
    assert "активирован" in message.last
    assert "Введите промокод" not in message.last
    state.set_state.assert_not_awaited()
    state.clear.assert_awaited_once()


async def test_inline_code_is_stripped_and_uppercased(promo):
    message = FakeMessage()
    state = FakeState()

    await referrals.promo_code_entry(message, state, command("  summer30  "))

    promo.get_promo_by_code.assert_awaited_once_with("SUMMER30")


async def test_an_invalid_inline_code_reports_the_same_error_as_the_prompted_flow(promo):
    promo.get_promo_by_code.return_value = None
    message = FakeMessage()
    state = FakeState()

    await referrals.promo_code_entry(message, state, command("BADCODE"))

    assert message.last == "❌ Промокод BADCODE недействителен."
    state.clear.assert_awaited_once()


# -- both entry points share one redemption path -----------------------------


async def test_inline_and_prompted_forms_produce_the_same_result(promo):
    """Typing the code in reply to the prompt is the same operation as `/promo CODE`."""
    inline_message = FakeMessage()
    await referrals.promo_code_entry(inline_message, FakeState(), command("summer30"))

    prompted_message = FakeMessage(text="summer30")
    await referrals.handle_promo_code(prompted_message, FakeState())

    assert inline_message.last == prompted_message.last

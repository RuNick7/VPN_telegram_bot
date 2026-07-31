"""
Who a successful payment credits.

The bug these exist for: crediting was gated on `telegram_id`, so a purchase
made from the website by an account that has never used Telegram was charged,
marked `processing_error`, and never applied -- with no alert anywhere,
because the admin notification lived inside the same gate.

`_resolve_payer` decides who paid; the helpers below decide which handle to
credit them by.
"""

from unittest.mock import AsyncMock, patch

import pytest

import payments.webhook as webhook

WEB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


def telegram_payer(telegram_id: int = 555) -> dict:
    return {"id": WEB_ID, "telegram_id": telegram_id, "referrer_tag": ""}


def website_payer() -> dict:
    """Signed up by email; no Telegram account exists for them at all."""
    return {"id": WEB_ID, "telegram_id": None, "referrer_tag": ""}


# -- working out who paid --------------------------------------------------


async def test_our_own_id_is_preferred(monkeypatch):
    """
    It is the only handle a website account has, and the lookup follows
    `merged_into` -- so a payment started before an account merge still
    credits the surviving row.
    """
    users = AsyncMock()
    users.get_user_by_uuid = AsyncMock(return_value=website_payer())
    monkeypatch.setattr(webhook, "_users", users)

    payer = await webhook._resolve_payer({"user_id": WEB_ID, "telegram_id": "0"})

    assert payer["id"] == WEB_ID
    users.get_user_by_uuid.assert_awaited_once_with(WEB_ID)


async def test_telegram_id_is_the_fallback(monkeypatch):
    """For payments created before the rework and still in flight."""
    users = AsyncMock()
    users.get_user_by_uuid = AsyncMock(return_value=None)
    users.get_user_by_id = AsyncMock(return_value=telegram_payer())
    monkeypatch.setattr(webhook, "_users", users)

    payer = await webhook._resolve_payer({"telegram_id": "555"})

    assert payer["telegram_id"] == 555


async def test_a_payer_with_no_row_is_still_creditable(monkeypatch):
    """The subscription path creates the row it needs."""
    users = AsyncMock()
    users.get_user_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(webhook, "_users", users)

    payer = await webhook._resolve_payer({"telegram_id": "555"})

    assert payer == {"id": None, "telegram_id": 555}


async def test_metadata_naming_nobody_resolves_to_nothing(monkeypatch):
    monkeypatch.setattr(webhook, "_users", AsyncMock())
    assert await webhook._resolve_payer({}) is None
    assert await webhook._resolve_payer({"telegram_id": "not-a-number"}) is None


# -- crediting traffic -----------------------------------------------------


async def test_traffic_goes_to_the_telegram_id_when_there_is_one(monkeypatch):
    lte = AsyncMock()
    monkeypatch.setattr(webhook, "_lte", lte)

    await webhook._credit_traffic(telegram_payer(), 10 * 1024**3)

    lte.credit_balance.assert_awaited_once_with(555, 10 * 1024**3)
    lte.credit_balance_by_user_id.assert_not_awaited()


async def test_traffic_goes_to_our_id_for_a_website_account(monkeypatch):
    """The case that used to be silently dropped."""
    lte = AsyncMock()
    monkeypatch.setattr(webhook, "_lte", lte)

    await webhook._credit_traffic(website_payer(), 10 * 1024**3)

    lte.credit_balance_by_user_id.assert_awaited_once_with(WEB_ID, 10 * 1024**3)
    lte.credit_balance.assert_not_awaited()


async def test_traffic_for_a_payer_with_no_identity_credits_nothing(monkeypatch):
    lte = AsyncMock()
    monkeypatch.setattr(webhook, "_lte", lte)

    assert await webhook._credit_traffic({"id": None, "telegram_id": None}, 1) is None
    lte.credit_balance.assert_not_awaited()
    lte.credit_balance_by_user_id.assert_not_awaited()


# -- extending a subscription ----------------------------------------------


async def test_a_telegram_user_goes_through_the_bots_path():
    with patch.object(webhook, "extend_subscription", AsyncMock(return_value="ok")) as extend:
        result = await webhook._extend_for_payer(telegram_payer(), 30)

    extend.assert_awaited_once_with(555, 30)
    assert result == "ok"


async def test_a_website_user_is_extended_by_internal_id():
    payer = website_payer()
    with patch.object(webhook, "extend_subscription_for_row", AsyncMock(return_value="ok")) as extend:
        result = await webhook._extend_for_payer(payer, 30)

    extend.assert_awaited_once_with(payer, 30)
    assert result == "ok"


async def test_an_unidentifiable_payer_reports_failure_not_success():
    """
    It must land in the `❌` branch so the payment is marked
    processing_error rather than succeeded.
    """
    result = await webhook._extend_for_payer({"id": None, "telegram_id": None}, 30)
    assert result.startswith("❌")


# -- referrals -------------------------------------------------------------


async def test_a_referrer_is_credited_for_a_website_purchase(monkeypatch):
    users = AsyncMock()
    users.get_user_by_uuid = AsyncMock(
        return_value={"id": WEB_ID, "telegram_id": None, "referrer_tag": "alice"}
    )
    users.award_referral_by_user_id = AsyncMock(return_value=True)
    monkeypatch.setattr(webhook, "_users", users)

    await webhook._award_referral_for_payer(website_payer())

    users.award_referral_by_user_id.assert_awaited_once_with("alice", WEB_ID)


async def test_no_referrer_means_nothing_is_credited(monkeypatch):
    users = AsyncMock()
    users.get_user_by_id = AsyncMock(return_value={"id": WEB_ID, "referrer_tag": ""})
    monkeypatch.setattr(webhook, "_users", users)

    await webhook._award_referral_for_payer(telegram_payer())

    users.award_referral.assert_not_awaited()


async def test_the_referrer_is_re_read_rather_than_trusted(monkeypatch):
    """
    The payer dict was assembled before the extension ran; `referrer_tag` may
    have been set in between.
    """
    users = AsyncMock()
    users.get_user_by_id = AsyncMock(
        return_value={"id": WEB_ID, "telegram_id": 555, "referrer_tag": "bob"}
    )
    users.award_referral = AsyncMock(return_value=True)
    monkeypatch.setattr(webhook, "_users", users)

    await webhook._award_referral_for_payer(telegram_payer())  # dict says ""

    users.award_referral.assert_awaited_once_with("bob", 555)


# -- gift counter ----------------------------------------------------------


async def test_gift_counter_uses_whichever_identity_exists(monkeypatch):
    users = AsyncMock()
    monkeypatch.setattr(webhook, "_users", users)

    await webhook._increment_gifted(telegram_payer())
    users.increment_gifted_subscriptions.assert_awaited_once_with(555)

    await webhook._increment_gifted(website_payer())
    users.increment_gifted_subscriptions_by_user_id.assert_awaited_once_with(WEB_ID)


# -- labelling -------------------------------------------------------------


@pytest.mark.parametrize(
    "payer, expected",
    [
        ({"telegram_id": 555, "id": WEB_ID}, "555"),
        ({"telegram_id": None, "id": WEB_ID}, WEB_ID),
        ({"telegram_id": None, "id": None}, "?"),
        (None, "?"),
    ],
)
def test_a_payer_is_always_nameable_in_a_log_line(payer, expected):
    assert webhook._payer_label(payer) == expected

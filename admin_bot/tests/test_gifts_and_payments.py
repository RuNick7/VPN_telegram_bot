"""
The two screens that exist because a failure used to be invisible.

A gift is handed over as a Telegram message the buyer may not be able to
receive, and a payment stuck out of `succeeded` means somebody paid and was
not credited. Neither was visible anywhere: the first had no record of who
bought it, the second was an id and a status.
"""

import time

from app.handlers.admin.gifts import build_gift_report
from app.handlers.admin.payments import PENDING_GRACE_SECONDS, build_report, needs_attention

NOW = int(time.time())


def gift(**kwargs) -> dict:
    base = dict(
        code="GIFT-ABC123",
        days=30,
        created_at=None,
        creator_id=None,
        buyer_email=None,
        buyer_tag=None,
        buyer_telegram_id=None,
        redeemed_at=None,
        taker_tag=None,
        taker_email=None,
    )
    return {**base, **kwargs}


def payment(**kwargs) -> dict:
    base = dict(
        payment_id="2f0a-1111",
        status="processing_error",
        purpose="subscription",
        days=30,
        created_at=NOW - 3600,
        updated_at=NOW - 3600,
        telegram_id=None,
        telegram_tag=None,
        email=None,
    )
    return {**base, **kwargs}


# -- gifts ------------------------------------------------------------------


def test_a_waiting_gift_is_marked_as_waiting():
    text = build_gift_report([gift()], {"total": 1, "redeemed": 0, "last_month": 1})
    assert "⏳" in text
    assert "GIFT-ABC123" in text


def test_a_redeemed_gift_names_who_used_it():
    text = build_gift_report(
        [gift(redeemed_at=NOW, taker_tag="friend")],
        {"total": 1, "redeemed": 1, "last_month": 1},
    )
    assert "✅" in text
    assert "@friend" in text


def test_a_website_buyer_is_named_by_their_address():
    # The whole reason this screen exists: that buyer has no Telegram, so
    # naming them by tag alone would show a dash for the person who paid.
    text = build_gift_report(
        [gift(buyer_email="customer@example.com")], {"total": 1, "redeemed": 0}
    )
    assert "customer@example.com" in text


def test_a_buyer_with_neither_handle_does_not_render_as_none():
    text = build_gift_report([gift()], {"total": 1, "redeemed": 0})
    assert "None" not in text


def test_no_gifts_says_so_rather_than_showing_an_empty_list():
    text = build_gift_report([], {"total": 0, "redeemed": 0, "last_month": 0})
    assert "Пока ни одного" in text


# -- payments ---------------------------------------------------------------


def test_a_failed_payment_needs_attention():
    assert needs_attention(payment(status="processing_error"), NOW) is True


def test_a_fresh_pending_payment_does_not():
    """The customer is still on the payment page. Not a problem yet."""
    assert needs_attention(payment(status="pending", updated_at=NOW - 60), NOW) is False


def test_an_old_pending_payment_does():
    stale = payment(status="pending", updated_at=NOW - PENDING_GRACE_SECONDS - 60)
    assert needs_attention(stale, NOW) is True


def test_a_stuck_processing_claim_needs_attention():
    # `claim_payment_processing` sets this and the webhook moves it on. Left
    # here, it means the crediting crashed halfway.
    assert needs_attention(payment(status="processing"), NOW) is True


def test_the_report_names_who_paid():
    text = build_report([payment(email="customer@example.com")], NOW)
    assert "customer@example.com" in text
    assert "2f0a-1111" in text


def test_the_report_says_what_the_money_was_for():
    text = build_report([payment(purpose="gift", days=90)], NOW)
    assert "подарок" in text
    assert "90" in text


def test_a_payment_with_no_user_says_so_rather_than_showing_a_blank():
    # This is the worst case and the one that most needs a human: money taken
    # and nobody to credit.
    text = build_report([payment()], NOW)
    assert "не определён" in text


def test_nothing_to_do_reads_as_nothing_to_do():
    text = build_report([payment(status="pending", updated_at=NOW - 60)], NOW)
    assert "Ничего" in text


def test_the_report_says_what_the_operator_can_actually_do():
    # Both levers, because neither is obvious: the webhook can be re-delivered
    # from the YooKassa dashboard, or the days credited by hand.
    text = build_report([payment()], NOW)
    assert "ЮKassa" in text
    assert "вручную" in text

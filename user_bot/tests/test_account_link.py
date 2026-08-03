"""
Attaching a Telegram account to a website account.

The link token is a credential: whoever holds it attaches *their* Telegram
account to the website account it names. So the tests below care about two
things -- that a token works exactly once, and that folding two accounts
together never costs the user days they paid for.
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers.account_link as link
from handlers.account_link import extract_link_token

DAY = 86400
GB = 1024**3
WEB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
TG_ID = "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301"


def row(**kwargs) -> dict:
    base = dict(
        id=TG_ID,
        telegram_id=555,
        subscription_ends=0,
        lte_paid_balance_bytes=0,
        gifted_subscriptions=0,
        referred_people=0,
        email=None,
        referrer_tag=None,
        remnawave_uuid=None,
        remnawave_username=None,
        trial_signup_granted=False,
        trial_link_granted=False,
    )
    return {**base, **kwargs}


@pytest.fixture
def repos(monkeypatch):
    users = AsyncMock()
    links = AsyncMock()
    expired = []

    # None means "already collected", which is the quiet case: most of these
    # tests are about the merge and should not have to say anything about the
    # bonus. The ones that are about it set a real expiry.
    users.grant_link_bonus = AsyncMock(return_value=None)

    monkeypatch.setattr(link, "_users", users)
    monkeypatch.setattr(link, "_links", links)
    monkeypatch.setattr(
        link, "_expire_leftover_panel_account", AsyncMock(side_effect=lambda u: expired.append(u))
    )
    return SimpleNamespace(users=users, links=links, expired=expired)


# -- the deep-link payload -------------------------------------------------


def test_a_link_payload_yields_its_token():
    assert extract_link_token("link_abc123") == "abc123"


def test_other_start_payloads_are_left_alone():
    """A referral or campaign deep link must fall through to /start."""
    for payload in ["ref_alice", "promo", "", None, "link_"]:
        assert extract_link_token(payload) is None


# -- redeeming -------------------------------------------------------------


async def test_an_unknown_token_changes_nothing(repos):
    repos.links.consume = AsyncMock(return_value=None)

    message = await link.link_account("nope", 555, "someone")

    assert "недействительна" in message
    repos.users.attach_telegram.assert_not_awaited()
    repos.users.apply_merge.assert_not_awaited()


async def test_a_replayed_token_changes_nothing(repos):
    """
    `consume` is atomic and returns None the second time, so a link forwarded
    to somebody else -- or prefetched by a mail client -- cannot attach a
    second Telegram account.
    """
    repos.links.consume = AsyncMock(side_effect=[WEB_ID, None])
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=None)
    repos.users.attach_telegram = AsyncMock(return_value=True)

    await link.link_account("token", 555, "someone")
    second = await link.link_account("token", 999, "intruder")

    assert "недействительна" in second
    repos.users.attach_telegram.assert_awaited_once()


async def test_a_telegram_user_without_an_account_just_gains_one(repos):
    """Nothing is merged on this path, so nothing can be lost."""
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=None)
    repos.users.attach_telegram = AsyncMock(return_value=True)

    message = await link.link_account("token", 555, "someone")

    repos.users.attach_telegram.assert_awaited_once_with(WEB_ID, 555, "someone")
    repos.users.apply_merge.assert_not_awaited()
    assert "привязан" in message


async def test_relinking_the_same_account_is_a_no_op(repos):
    """Pressing the link twice must not merge an account into itself."""
    same = row(id=WEB_ID, telegram_id=555)
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=same)
    repos.users.get_user_by_id = AsyncMock(return_value=same)

    message = await link.link_account("token", 555, "someone")

    repos.users.apply_merge.assert_not_awaited()
    assert "уже привязан" in message


# -- the bonus for connecting a second identity ----------------------------


async def test_a_brand_new_telegram_account_earns_the_bonus(repos):
    """
    The one path it is paid on. This Telegram user had no row at all, so they
    have never collected a signup trial and nothing has been summed -- the
    website account genuinely gains days it did not have.
    """
    now = int(time.time())
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=None)
    repos.users.attach_telegram = AsyncMock(return_value=True)
    repos.users.grant_link_bonus = AsyncMock(return_value=now + 11 * DAY)

    message = await link.link_account("token", 555, "someone")

    repos.users.grant_link_bonus.assert_awaited_once()
    assert repos.users.grant_link_bonus.await_args.args[0] == WEB_ID
    assert "Начислено" in message
    assert "11 дн." in message


async def test_merging_two_real_accounts_pays_no_bonus(repos):
    """
    Their days have just been added together, which is the same 7 + 7 the
    bonus exists to hand out. Paying on top would put 21 free days within
    reach of anyone who registered twice on purpose.
    """
    now = int(time.time())
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(
        return_value=row(id=WEB_ID, telegram_id=None, subscription_ends=now + 7 * DAY)
    )
    repos.users.get_user_by_id = AsyncMock(
        return_value=row(id=TG_ID, subscription_ends=now + 7 * DAY)
    )

    await link.link_account("token", 555, "someone")

    repos.users.grant_link_bonus.assert_not_awaited()
    plan = repos.users.apply_merge.await_args.args[0]
    assert (plan.subscription_ends - now) // DAY == 14


async def test_a_merge_spends_the_bonus_even_when_it_paid_nothing(repos):
    """
    The second identity has been connected, which is what the bonus is for.
    Leaving the flag clear would let the same account collect it afterwards by
    confirming an email as well.
    """
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=row(id=TG_ID))

    await link.link_account("token", 555, "someone")

    assert repos.users.apply_merge.await_args.args[0].trial_link_granted is True


async def test_an_already_collected_bonus_is_not_announced_twice(repos):
    """`grant_link_bonus` returning None means the flag was already set."""
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=None)
    repos.users.attach_telegram = AsyncMock(return_value=True)
    repos.users.grant_link_bonus = AsyncMock(return_value=None)

    message = await link.link_account("token", 555, "someone")

    assert "привязан" in message
    assert "Начислено" not in message


# -- merging ---------------------------------------------------------------


async def test_days_from_both_accounts_add_up(repos):
    now = int(time.time())
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(
        return_value=row(id=WEB_ID, telegram_id=None, subscription_ends=now + 30 * DAY)
    )
    repos.users.get_user_by_id = AsyncMock(
        return_value=row(id=TG_ID, subscription_ends=now + 14 * DAY)
    )

    message = await link.link_account("token", 555, "someone")

    plan = repos.users.apply_merge.await_args.args[0]
    assert (plan.subscription_ends - now) // DAY == 44
    assert "объединены" in message
    assert "44" in message


async def test_purchased_traffic_survives_a_merge(repos):
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(
        return_value=row(id=WEB_ID, telegram_id=None, lte_paid_balance_bytes=5 * GB)
    )
    repos.users.get_user_by_id = AsyncMock(
        return_value=row(id=TG_ID, lte_paid_balance_bytes=3 * GB)
    )

    await link.link_account("token", 555, "someone")

    assert repos.users.apply_merge.await_args.args[0].lte_paid_balance_bytes == 8 * GB


async def test_the_telegram_row_is_the_one_that_survives(repos):
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=row(id=TG_ID))

    await link.link_account("token", 555, "someone")

    plan = repos.users.apply_merge.await_args.args[0]
    assert plan.survivor_id == TG_ID
    assert plan.absorbed_id == WEB_ID


async def test_the_leftover_panel_account_is_expired(repos):
    """
    Its days were just added to the survivor. Left live, the user would hold
    two working links covering the same period.
    """
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(
        return_value=row(id=WEB_ID, telegram_id=None, remnawave_uuid="panel-web")
    )
    repos.users.get_user_by_id = AsyncMock(return_value=row(id=TG_ID, remnawave_uuid="panel-tg"))

    await link.link_account("token", 555, "someone")

    assert repos.expired == ["panel-web"]


async def test_no_panel_account_is_touched_when_there_is_nothing_left_over(repos):
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(
        return_value=row(id=WEB_ID, telegram_id=None, remnawave_uuid="panel-web")
    )
    repos.users.get_user_by_id = AsyncMock(return_value=row(id=TG_ID, remnawave_uuid=None))

    await link.link_account("token", 555, "someone")

    # The survivor had no profile, so it adopts this one instead of orphaning it.
    assert repos.expired == []
    assert repos.users.apply_merge.await_args.args[0].adopt_panel_uuid == "panel-web"


async def test_a_token_pointing_at_a_deleted_account_fails_safely(repos):
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=None)

    message = await link.link_account("token", 555, "someone")

    repos.users.apply_merge.assert_not_awaited()
    assert "не найден" in message


async def test_an_account_already_bound_elsewhere_is_refused(repos):
    """
    `attach_telegram` only fills an empty slot, so a second link attempt
    cannot move an account off the Telegram user it belongs to.
    """
    repos.links.consume = AsyncMock(return_value=WEB_ID)
    repos.users.get_user_by_uuid = AsyncMock(return_value=row(id=WEB_ID, telegram_id=None))
    repos.users.get_user_by_id = AsyncMock(return_value=None)
    repos.users.attach_telegram = AsyncMock(return_value=False)

    message = await link.link_account("token", 555, "someone")

    assert "уже привязан к другому" in message

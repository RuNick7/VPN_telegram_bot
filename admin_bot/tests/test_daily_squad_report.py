"""
The daily headcount.

It replaced a "squad is 75% full" alert. That alert made sense when users were
split across capped squads and crossing the cap forced the code to create
another one; neither is true now, so the number is information rather than a
fault. These tests mostly pin that it stays information -- no thresholds, no
alarm wording, and sent on a quiet day too.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.scheduler.jobs.daily_squad_report import format_report, run_daily_squad_report


def report(**kwargs) -> str:
    defaults = dict(
        squad_members={"internal": 420, "free": 130, "lte": 12},
        paid_squad_name="internal",
        tier_counts={"paid": 415, "free": 128, "unknown": 3},
        active_subscriptions=418,
        actions={"demoted": 8, "blocked": 12, "promoted": 5},
    )
    return format_report(**{**defaults, **kwargs})


# -- what it says ----------------------------------------------------------


def test_the_paid_squad_headcount_is_the_headline():
    """The number an operator uses to decide whether to buy another server."""
    text = report()
    assert "internal" in text
    assert "420" in text


def test_the_other_squads_are_shown_as_context():
    text = report()
    assert "free" in text and "130" in text
    assert "lte" in text and "12" in text


def test_our_own_counts_are_shown_beside_the_panels():
    """
    Two sources on purpose: squad membership is what the panel believes,
    tier counts are what our database believes. The day they disagree is worth
    seeing side by side rather than discovering during an incident.
    """
    text = report()
    assert "418" in text   # active subscriptions, from our database
    assert "415" in text   # paid tier, from our database


def test_a_renamed_paid_squad_is_still_found():
    text = report(squad_members={"subscribers": 7}, paid_squad_name="subscribers")
    assert "7" in text


def test_a_paid_squad_missing_from_the_panel_reads_as_zero():
    """
    Better than omitting the line: zero where hundreds were yesterday is a
    visible problem, and a missing line is not.
    """
    text = report(squad_members={"free": 5})
    assert "0" in text


def test_it_carries_no_threshold_or_alarm_wording():
    """
    The point of the change. Capacity is the operator's call now, so this must
    not look like something went wrong.
    """
    text = report().lower()
    for word in ("превыш", "переполн", "предупрежд", "внимание", "⚠", "❌"):
        assert word not in text


# -- the day's actions -----------------------------------------------------
#
# These arrived as their own message the moment they happened, every few
# minutes, all day. They are counted here instead.


def test_the_days_actions_are_counted():
    text = report(actions={"demoted": 8, "blocked": 12, "promoted": 5})
    assert "понижено в FREE: 8" in text
    assert "заблокировано по трафику: 12" in text
    assert "возвращено в платный: 5" in text


def test_an_action_nothing_did_is_printed_as_zero():
    """
    A missing line reads as "nothing happened". The difference that matters is
    "nothing happened" versus "this stopped being counted", and only an
    explicit zero tells them apart.
    """
    text = report(actions={"demoted": 3})
    assert "заблокировано по трафику: 0" in text
    assert "повторный обрыв соединения: 0" in text


def test_a_quiet_day_still_shows_the_whole_list():
    text = report(actions={})
    assert "понижено в FREE: 0" in text
    assert "возвращено в платный: 0" in text


def test_an_unrecognised_action_is_shown_rather_than_dropped():
    """
    A monitor recording an outcome this report has no label for is a mistake
    worth seeing. Swallowing it would hide the number entirely.
    """
    text = report(actions={"vaporised": 2})
    assert "vaporised: 2" in text


def test_an_unrecognised_action_cannot_inject_markup():
    """The keys come from code, but the report is sent as HTML."""
    assert "&lt;b&gt;oops" in report(actions={"<b>oops": 1})


# -- when it runs ----------------------------------------------------------


@pytest.fixture
def job(monkeypatch):
    client = AsyncMock()
    client.list_internal_squads = AsyncMock(
        return_value=[{"name": "internal", "info": {"membersCount": 42}}]
    )
    users = AsyncMock()
    users.get_stats = AsyncMock(return_value={"active": 40})
    lte = AsyncMock()
    lte.get_tier_counts = AsyncMock(return_value={"paid": 40})
    enforcement = AsyncMock()
    enforcement.summary_since = AsyncMock(return_value={"demoted": 2})
    enforcement.prune = AsyncMock(return_value=0)
    send = AsyncMock()

    monkeypatch.setattr(
        "app.scheduler.jobs.daily_squad_report.RemnawaveClient", lambda *a, **k: client
    )
    monkeypatch.setattr("app.scheduler.jobs.daily_squad_report._users", users)
    monkeypatch.setattr("app.scheduler.jobs.daily_squad_report._lte", lte)
    monkeypatch.setattr("app.scheduler.jobs.daily_squad_report._enforcement", enforcement)
    monkeypatch.setattr("app.scheduler.jobs.daily_squad_report.send_admin_message", send)
    return client, send, enforcement


async def test_a_quiet_day_still_sends_a_report(job):
    """
    A report that only arrives when something is wrong teaches you to read its
    absence as "fine" -- which is exactly how a job that stopped running hides.
    """
    _client, send, _enforcement = job
    await run_daily_squad_report()
    send.assert_awaited_once()


async def test_the_panel_connection_is_always_closed(job):
    client, _send, _enforcement = job
    await run_daily_squad_report()
    client.close.assert_awaited_once()


async def test_a_panel_failure_is_reported_not_raised(job):
    """The scheduler has to keep ticking."""
    client, send, _enforcement = job
    client.list_internal_squads = AsyncMock(side_effect=RuntimeError("panel down"))

    await run_daily_squad_report()  # must not raise

    assert "Не удалось" in send.await_args.args[0]
    client.close.assert_awaited_once()


async def test_a_failure_to_report_the_failure_does_not_raise_either(job):
    client, send, _enforcement = job
    client.list_internal_squads = AsyncMock(side_effect=RuntimeError("panel down"))
    send.side_effect = RuntimeError("telegram down")

    await run_daily_squad_report()  # must not raise


# -- the markup has to survive the trip ------------------------------------


async def test_the_report_is_sent_as_html_not_escaped_into_a_code_block(job):
    """
    `send_admin_message` escapes its argument and wraps it in <pre> by default,
    which is right for an error dump and wrong for this: the report arrived
    with its own <b> tags visible inside a monospace block.
    """
    _client, send, _enforcement = job
    await run_daily_squad_report()
    assert send.await_args.kwargs.get("html_body") is True


async def test_a_squad_named_with_angle_brackets_does_not_break_the_message():
    """
    Squad names come from the panel. With html_body on, an unescaped one would
    make Telegram reject the whole report.
    """
    text = report(squad_members={"internal": 1, "<b>oops": 2})
    assert "<b>oops" not in text
    assert "&lt;b&gt;oops" in text

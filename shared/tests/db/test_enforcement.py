"""
The enforcement log behind the daily report.

Its whole reason for existing is that it is not a counter in memory:
admin_bot restarts on every deploy, and the monitors it replaces messaged the
admin chat on every pass so nothing was ever lost. Move the counting to a
daily report and durability stops being optional -- a total that quietly drops
the hours before a restart is a report that lies without looking wrong.

So the properties worth pinning are the boring ones: a row survives, the
window is honoured at its edges, and the prune only takes what it should.
"""

from tgvpn_shared.db import EnforcementRepository
from tgvpn_shared.db.pool import get_pool

log = EnforcementRepository()

JOB = "lte_traffic_monitor"
DAY = 24 * 60 * 60


async def _backdate(seconds: int) -> None:
    """Age every row by `seconds`, so windows can be tested without waiting."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE enforcement_events SET ts = ts - ($1 * INTERVAL '1 second')", seconds
    )


# -- counting --------------------------------------------------------------


async def test_nothing_recorded_counts_as_nothing():
    assert await log.summary_since(DAY) == {}


async def test_actions_are_counted_by_kind():
    for action in ("blocked", "blocked", "unblocked"):
        await log.record(JOB, action, 104)

    assert await log.summary_since(DAY) == {"blocked": 2, "unblocked": 1}


async def test_two_jobs_writing_the_same_action_are_added_together():
    """
    The report counts what happened, not who did it. Both monitors can demote
    somebody, and an operator reading "понижено в FREE: 8" wants eight.
    """
    await log.record("subscription_expire_monitor", "demoted", 1)
    await log.record("lte_traffic_monitor", "demoted", 2)

    assert (await log.summary_since(DAY))["demoted"] == 2


# -- the window ------------------------------------------------------------


async def test_something_older_than_the_window_is_not_counted():
    await log.record(JOB, "blocked", 104)
    await _backdate(DAY + 60)

    assert await log.summary_since(DAY) == {}


async def test_something_inside_the_window_is_still_counted():
    """The other edge: a report at 10:00 must see yesterday evening's cut-offs."""
    await log.record(JOB, "blocked", 104)
    await _backdate(DAY - 600)

    assert await log.summary_since(DAY) == {"blocked": 1}


# -- naming names ----------------------------------------------------------


async def test_the_subjects_of_an_action_can_be_listed():
    await log.record(JOB, "blocked", 104)
    await log.record(JOB, "blocked", 105)
    await log.record(JOB, "unblocked", 106)

    assert set(await log.recent(DAY, "blocked")) == {"104", "105"}


async def test_a_subject_that_was_never_known_is_not_listed_as_blank():
    """A website account reaches some paths with no handle worth printing."""
    await log.record(JOB, "blocked", None)

    assert await log.recent(DAY, "blocked") == []
    assert (await log.summary_since(DAY))["blocked"] == 1


async def test_an_absurdly_long_subject_does_not_reach_the_column():
    await log.record(JOB, "blocked", "x" * 5000)

    assert len((await log.recent(DAY, "blocked"))[0]) == 200


# -- pruning ---------------------------------------------------------------


async def test_pruning_leaves_what_is_still_in_range():
    await log.record(JOB, "blocked", 104)

    assert await log.prune(30) == 0
    assert (await log.summary_since(DAY))["blocked"] == 1


async def test_pruning_takes_what_has_aged_out():
    await log.record(JOB, "blocked", 104)
    await _backdate(31 * DAY)

    assert await log.prune(30) == 1
    assert await log.summary_since(365 * DAY) == {}

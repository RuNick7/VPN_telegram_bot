"""
Job-run bookkeeping.

This is what makes a dead enforcement job detectable. With the FREE tier on,
`subscription_expire_monitor` is the only thing cutting off lapsed
subscriptions -- and a crashed scheduler, an exception every tick, and a job
that was never registered all look identical from outside: nothing happens,
nothing complains.
"""

from tgvpn_shared.db import JobRunRepository

jobs = JobRunRepository()

JOB = "subscription_expire_monitor"


async def test_unknown_job_has_no_record():
    assert await jobs.get(JOB) is None


async def test_success_is_recorded_with_a_duration():
    await jobs.record_success(JOB, duration_ms=1234)
    state = await jobs.get(JOB)
    assert state["last_success_at"] is not None
    assert state["last_attempt_at"] is not None
    assert state["consecutive_failures"] == 0
    assert state["last_duration_ms"] == 1234
    assert state["last_error"] is None


async def test_failures_accumulate():
    assert await jobs.record_failure(JOB, "boom") == 1
    assert await jobs.record_failure(JOB, "boom again") == 2
    state = await jobs.get(JOB)
    assert state["last_error"] == "boom again"


async def test_a_success_clears_the_failure_streak():
    await jobs.record_failure(JOB, "boom")
    await jobs.record_failure(JOB, "boom")
    await jobs.record_success(JOB)

    state = await jobs.get(JOB)
    assert state["consecutive_failures"] == 0
    assert state["last_error"] is None


async def test_failure_does_not_touch_the_last_success_time():
    """
    The property staleness detection depends on.

    A job failing every five minutes has a perfectly fresh *attempt*; only
    tracking success separately lets the monitor still call it stale.
    """
    await jobs.record_success(JOB)
    success_at = (await jobs.get(JOB))["last_success_at"]

    await jobs.record_failure(JOB, "boom")

    state = await jobs.get(JOB)
    assert state["last_success_at"] == success_at
    assert state["last_attempt_at"] >= success_at


async def test_a_job_that_never_ran_counts_as_stale():
    """
    "Never registered" is as broken as "crashed", and far easier to do by
    accident -- so the absence of a row must alert rather than pass silently.
    """
    stale = await jobs.find_stale(JOB, max_age_seconds=600)
    assert stale is not None
    assert stale["last_success_at"] is None


async def test_a_recently_succeeded_job_is_not_stale():
    await jobs.record_success(JOB)
    assert await jobs.find_stale(JOB, max_age_seconds=600) is None


async def test_a_job_that_only_ever_fails_is_stale():
    await jobs.record_failure(JOB, "boom")
    stale = await jobs.find_stale(JOB, max_age_seconds=600)
    assert stale is not None
    assert stale["consecutive_failures"] == 1
    assert stale["last_error"] == "boom"


async def test_success_older_than_the_threshold_is_stale():
    await jobs.record_success(JOB)
    # Zero tolerance: any success is already in the past.
    assert await jobs.find_stale(JOB, max_age_seconds=0) is not None


async def test_jobs_are_tracked_independently():
    await jobs.record_success("job_a")
    await jobs.record_failure("job_b", "boom")

    assert await jobs.find_stale("job_a", 600) is None
    assert await jobs.find_stale("job_b", 600) is not None
    assert [row["job_name"] for row in await jobs.get_all()] == ["job_a", "job_b"]


async def test_long_errors_are_truncated_rather_than_rejected():
    await jobs.record_failure(JOB, "x" * 5000)
    assert len((await jobs.get(JOB))["last_error"]) <= 1000

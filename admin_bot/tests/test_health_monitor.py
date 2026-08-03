"""
Staleness detection for the enforcement jobs.

This is the check the FREE tier's safety rests on. With it enabled, panel
accounts no longer expire on their own, so `subscription_expire_monitor` is
the only thing cutting off lapsed subscriptions -- and a job that stops
running produces no error, no log line, and no visible symptom until someone
notices they never lost access.
"""

import time
from unittest.mock import AsyncMock

import pytest

from app.scheduler.jobs import lte_traffic_monitor, subscription_expire_monitor
from app.scheduler.jobs.service_health_monitor import (
    _check_jobs,
    _stale_after_seconds,
    format_stale_job,
)

JOB = subscription_expire_monitor.JOB_NAME


def stale_state(*, minutes_ago: int | None, failures: int = 0, error: str | None = None) -> dict:
    """A `job_runs` row as `find_stale` would return it."""
    return {
        "job_name": JOB,
        "last_attempt_at": int(time.time()),
        "last_success_at": None if minutes_ago is None else int(time.time()) - minutes_ago * 60,
        "last_error": error,
        "consecutive_failures": failures,
        "last_duration_ms": None,
    }


@pytest.fixture
def free_tier_on(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "free_tier_enabled", True)
    monkeypatch.setattr(settings, "lte_enabled", False)


def test_threshold_is_a_multiple_of_the_job_interval(monkeypatch):
    """One missed tick is scheduling jitter; two in a row is not."""
    from app.config.settings import settings

    monkeypatch.setattr(settings, "monitor_interval_minutes", 5)
    monkeypatch.setattr(settings, "job_stale_interval_multiplier", 2.0)
    assert _stale_after_seconds() == 600


async def test_a_healthy_job_raises_nothing(free_tier_on):
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=None)
    assert await _check_jobs(jobs) == []


async def test_a_stale_job_is_reported(free_tier_on):
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=stale_state(minutes_ago=25))

    issues = await _check_jobs(jobs)
    assert len(issues) == 1
    assert JOB in issues[0]
    assert "25" in issues[0]


async def test_a_job_that_never_succeeded_is_reported(free_tier_on):
    """
    Covers a job that was never scheduled at all -- easy to do by accident and
    just as broken as a crash, but with nothing to notice.
    """
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=stale_state(minutes_ago=None))

    issues = await _check_jobs(jobs)
    assert "ни одного успешного прохода" in issues[0]


async def test_disabled_features_are_not_watched(monkeypatch):
    """A job that is switched off is correctly absent, not faulty."""
    from app.config.settings import settings

    monkeypatch.setattr(settings, "free_tier_enabled", False)
    monkeypatch.setattr(settings, "lte_enabled", False)

    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=stale_state(minutes_ago=99))

    assert await _check_jobs(jobs) == []
    jobs.find_stale.assert_not_awaited()


async def test_both_jobs_are_watched_when_both_are_on(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "free_tier_enabled", True)
    monkeypatch.setattr(settings, "lte_enabled", True)

    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=stale_state(minutes_ago=25))

    assert len(await _check_jobs(jobs)) == 2
    watched = {call.args[0] for call in jobs.find_stale.await_args_list}
    assert watched == {subscription_expire_monitor.JOB_NAME, lte_traffic_monitor.JOB_NAME}


def test_report_includes_the_failure_reason():
    """
    A job failing every tick still counts as stale, and the message has to say
    why -- otherwise the admin knows only that something stopped.
    """
    message = format_stale_job(
        JOB, stale_state(minutes_ago=25, failures=3, error="Remnawave panel unreachable"), 600
    )
    assert "подряд ошибок: 3" in message
    assert "Remnawave panel unreachable" in message


def test_report_truncates_a_huge_error():
    message = format_stale_job(JOB, stale_state(minutes_ago=25, error="x" * 5000), 600)
    assert len(message) < 600


# -- a job that has not run yet --------------------------------------------


def never_ran() -> dict:
    """
    What `find_stale` returns for a job with no row at all.

    Distinct from "attempted and never succeeded": there is no attempt either,
    which right after a start means the job has not had its first tick.
    """
    return {
        "job_name": JOB,
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "consecutive_failures": 0,
        "last_duration_ms": None,
    }


async def test_a_job_that_has_not_run_yet_is_not_reported_right_after_a_start(free_tier_on):
    """
    The false alarm this fixes.

    Both monitors run on the same interval, so whichever fires first sees an
    empty `job_runs` and calls the other dead. Switching LTE_ENABLED on
    produced exactly that: an alert for a job that ran fine four minutes later.
    """
    from app.scheduler.jobs import service_health_monitor

    service_health_monitor._started_at = time.time()
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=never_ran())

    assert await _check_jobs(jobs) == []


async def test_a_job_that_has_still_not_run_much_later_is_reported(free_tier_on, monkeypatch):
    """
    Past the threshold, silence really is a fault -- a job that was never
    registered looks identical to one that is working until somebody checks.
    """
    from app.scheduler.jobs import service_health_monitor

    monkeypatch.setattr(service_health_monitor, "_started_at", time.time() - 3600)
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=never_ran())

    issues = await _check_jobs(jobs)
    assert "ни одного успешного прохода" in issues[0]


async def test_a_job_that_has_run_and_failed_is_reported_immediately(free_tier_on):
    """
    The grace period is only for jobs with no attempt at all. One that has run
    and never succeeded is broken now, whatever the process uptime.
    """
    from app.scheduler.jobs import service_health_monitor

    service_health_monitor._started_at = time.time()
    jobs = AsyncMock()
    jobs.find_stale = AsyncMock(return_value=stale_state(minutes_ago=None, error="boom"))

    issues = await _check_jobs(jobs)
    assert "ни одного успешного прохода" in issues[0]
    assert "boom" in issues[0]

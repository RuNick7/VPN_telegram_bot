"""
The promise the schedulers make: these never raise.

It is not a style rule. APScheduler drops a job whose coroutine raises out of
the entry point, and `run_catchup_sweep` awaits one of these at start-up, where
an escaping exception becomes "Task exception was never retrieved" and nothing
runs afterwards.

The failure that proved it: the panel timed out, which the body handles exactly
as intended -- record it, log it, message the chat. Recording it hit a database
that was down in the same outage, and that second exception escaped. An outage
big enough to take both is precisely when a monitor must not compound it.
"""

import pytest

from app.scheduler.jobs import lte_traffic_monitor, subscription_expire_monitor


class Boom(Exception):
    """Stands in for a database that is down while the panel is also down."""


def exploding(sink: list, label: str):
    """
    A stand-in that records that it was reached before failing.

    Both feature flags default to False, so a monkeypatch that silently did
    not apply would make every test here pass by returning early and proving
    nothing. The sink is what rules that out.
    """

    async def explode(*args, **kwargs):
        sink.append(label)
        raise Boom(label)

    return explode


@pytest.mark.asyncio
async def test_the_expiry_monitor_swallows_a_failing_failure_path(monkeypatch, caplog):
    reached: list[str] = []
    monkeypatch.setattr(subscription_expire_monitor.settings, "free_tier_enabled", True)
    monkeypatch.setattr(subscription_expire_monitor, "_run", exploding(reached, "panel"))
    monkeypatch.setattr(
        subscription_expire_monitor._jobs, "record_failure", exploding(reached, "database")
    )
    monkeypatch.setattr(
        subscription_expire_monitor, "send_admin_message", exploding(reached, "chat")
    )

    await subscription_expire_monitor.run_subscription_expire_monitor()
    assert reached == ["panel", "database"]


@pytest.mark.asyncio
async def test_the_catchup_sweep_is_safe_to_await_at_startup(monkeypatch):
    """Where the escaping exception actually landed."""

    reached: list[str] = []
    monkeypatch.setattr(subscription_expire_monitor.settings, "free_tier_enabled", True)
    monkeypatch.setattr(subscription_expire_monitor, "_run", exploding(reached, "panel"))
    monkeypatch.setattr(
        subscription_expire_monitor._jobs, "record_failure", exploding(reached, "database")
    )
    monkeypatch.setattr(
        subscription_expire_monitor, "send_admin_message", exploding(reached, "chat")
    )

    await subscription_expire_monitor.run_catchup_sweep()
    assert reached == ["panel", "database"]


@pytest.mark.asyncio
async def test_the_traffic_monitor_swallows_a_failing_failure_path(monkeypatch):
    reached: list[str] = []
    monkeypatch.setattr(lte_traffic_monitor.settings, "lte_enabled", True)
    monkeypatch.setattr(lte_traffic_monitor, "_run", exploding(reached, "panel"))
    monkeypatch.setattr(lte_traffic_monitor._jobs, "record_failure", exploding(reached, "database"))
    monkeypatch.setattr(lte_traffic_monitor, "send_admin_message", exploding(reached, "chat"))

    await lte_traffic_monitor.run_lte_traffic_monitor()
    assert reached == ["panel", "database"]


@pytest.mark.asyncio
async def test_a_successful_run_that_cannot_be_recorded_still_returns(monkeypatch):
    """
    The other half. Bookkeeping failing after a *successful* pass must not
    undo the pass -- the work already landed in the panel.
    """

    reached: list[str] = []

    async def fine(*args, **kwargs):
        reached.append("pass")
        return 0, 0, 0

    monkeypatch.setattr(lte_traffic_monitor.settings, "lte_enabled", True)
    monkeypatch.setattr(lte_traffic_monitor, "_run", fine)
    monkeypatch.setattr(lte_traffic_monitor._jobs, "record_success", exploding(reached, "database"))

    await lte_traffic_monitor.run_lte_traffic_monitor()
    assert reached == ["pass", "database"]

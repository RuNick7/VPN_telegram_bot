"""
What still interrupts an operator, and what waits for the morning.

Both squad monitors run every few minutes and used to message the admin chat
on any pass that changed anything. In a service of any size that is a
notification per routine demotion, all day. The cost is not the noise itself
-- it is that the failure alerts sitting in the same chat stop being read,
which is the only reason the chat exists.

So the split is: routine outcomes are written to `enforcement_events` and
counted once by the daily report; anything that means enforcement is *not
happening* still goes out immediately. These tests pin both halves, because
either one silently flipping back is invisible until it matters.
"""

import pytest

from app.scheduler.jobs import lte_traffic_monitor, subscription_expire_monitor


class Recorder:
    """Stands in for the enforcement log and the admin chat at once."""

    def __init__(self):
        self.recorded: list[tuple[str, str, str]] = []
        self.messages: list[str] = []

    async def record(self, job, action, subject=None):
        self.recorded.append((job, action, str(subject)))

    async def send(self, text, *args, **kwargs):
        self.messages.append(text)


@pytest.fixture
def lte(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(lte_traffic_monitor.settings, "lte_enabled", True)
    # Both monitors write through the one repository instance that
    # `record_action` holds, so patching it here covers either of them.
    monkeypatch.setattr(subscription_expire_monitor._enforcement, "record", rec.record)
    monkeypatch.setattr(lte_traffic_monitor, "send_admin_message", rec.send)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(lte_traffic_monitor._jobs, "record_success", noop)
    return rec


@pytest.fixture
def expiry(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(subscription_expire_monitor.settings, "free_tier_enabled", True)
    monkeypatch.setattr(subscription_expire_monitor._enforcement, "record", rec.record)
    monkeypatch.setattr(subscription_expire_monitor, "send_admin_message", rec.send)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(subscription_expire_monitor._jobs, "record_success", noop)
    return rec


def returning(value):
    async def run(*args, **kwargs):
        return value

    return run


# -- the routine case ------------------------------------------------------


async def test_a_pass_that_blocked_people_says_nothing(lte, monkeypatch):
    """The message this change was about."""
    monkeypatch.setattr(lte_traffic_monitor, "_run", returning((12, 3, 0)))

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert lte.messages == []


async def test_a_pass_that_demoted_people_says_nothing(expiry, monkeypatch):
    monkeypatch.setattr(subscription_expire_monitor, "_run", returning((8, 5, [])))

    await subscription_expire_monitor.run_subscription_expire_monitor()

    assert expiry.messages == []


# -- what still gets through -----------------------------------------------


async def test_users_the_traffic_monitor_could_not_process_are_reported_at_once(
    lte, monkeypatch
):
    """
    Each one is a user whose quota is not being enforced right now. Rare, and
    exactly the kind of thing a daily total would bury.
    """
    monkeypatch.setattr(lte_traffic_monitor, "_run", returning((0, 0, 4)))

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert len(lte.messages) == 1
    assert "4" in lte.messages[0]


async def test_users_the_expiry_monitor_could_not_process_are_named(expiry, monkeypatch):
    monkeypatch.setattr(
        subscription_expire_monitor, "_run", returning((0, 0, ["104: panel timeout"]))
    )

    await subscription_expire_monitor.run_subscription_expire_monitor()

    assert len(expiry.messages) == 1
    assert "104: panel timeout" in expiry.messages[0]


async def test_a_long_failure_list_is_summarised_rather_than_dumped(expiry, monkeypatch):
    failures = [f"{i}: boom" for i in range(20)]
    monkeypatch.setattr(subscription_expire_monitor, "_run", returning((0, 0, failures)))

    await subscription_expire_monitor.run_subscription_expire_monitor()

    assert "и ещё 15" in expiry.messages[0]


async def test_a_pass_with_both_reports_only_the_failures(expiry, monkeypatch):
    """
    The counts are in the daily report. Repeating them beside an alert would
    put back exactly the message this change removed.
    """
    monkeypatch.setattr(subscription_expire_monitor, "_run", returning((8, 5, ["104: boom"])))

    await subscription_expire_monitor.run_subscription_expire_monitor()

    assert "понижено" not in expiry.messages[0]


async def test_a_quiet_pass_says_nothing_either(lte, monkeypatch):
    monkeypatch.setattr(lte_traffic_monitor, "_run", returning((0, 0, 0)))

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert lte.messages == []


# -- the counts survive a restart ------------------------------------------


def _one_user_pass(monkeypatch, outcomes: list[str | None]):
    """
    Wire `lte_traffic_monitor._run` up to walk one panel user per outcome.

    Everything outside the loop is stubbed; what is under test is the
    bookkeeping the loop does with whatever `_reconcile_user` returns.
    """
    from tgvpn_shared.squads import SquadRoles

    users = [{"id": 100 + i} for i in range(len(outcomes))]

    async def walk(*args, **kwargs):
        for user in users:
            yield user

    class Client:
        iter_all_users = staticmethod(walk)
        list_nodes = staticmethod(returning([]))
        close = staticmethod(returning(None))

    client = Client()

    monkeypatch.setattr(lte_traffic_monitor, "RemnawaveClient", lambda *a, **k: client)
    monkeypatch.setattr(
        lte_traffic_monitor,
        "resolve_squad_roles",
        returning(SquadRoles(free_uuid="free-1", lte_uuid="lte-1", paid_uuid="int-1")),
    )
    monkeypatch.setattr(lte_traffic_monitor, "warn_about_stuck_accounts", returning([]))
    monkeypatch.setattr(lte_traffic_monitor, "resolve_lte_nodes", lambda nodes: {"node-a"})
    monkeypatch.setattr(
        lte_traffic_monitor._users, "get_subscription_ends_map", returning({})
    )
    monkeypatch.setattr(
        lte_traffic_monitor._users, "get_subscription_map_by_panel_uuid", returning({})
    )
    monkeypatch.setattr(
        lte_traffic_monitor,
        "resolve_subject",
        lambda user, *a: subscription_expire_monitor.Subject(int(user["id"]), None, 0),
    )

    remaining = list(outcomes)

    async def reconcile(*args, **kwargs):
        return remaining.pop(0)

    monkeypatch.setattr(lte_traffic_monitor, "_reconcile_user", reconcile)


async def test_every_outcome_is_written_down_where_a_restart_cannot_lose_it(
    lte, monkeypatch
):
    """
    The reason this is a table and not a counter in memory: admin_bot restarts
    on every deploy, and a daily total that quietly drops the hours before one
    is a report that lies without ever looking wrong.
    """
    _one_user_pass(monkeypatch, ["blocked", "unblocked", "recut"])

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert [action for _job, action, _subject in lte.recorded] == [
        "blocked", "unblocked", "recut",
    ]
    assert lte.messages == []


async def test_a_user_needing_nothing_is_not_written_down(lte, monkeypatch):
    """
    Most users, most passes. A row each would make the table a log of the
    monitor running rather than of anything it did.
    """
    _one_user_pass(monkeypatch, [None, None])

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert lte.recorded == []


async def test_the_recorded_subject_is_the_user_it_happened_to(lte, monkeypatch):
    """Only ever read by a human, but useless if it is not there."""
    _one_user_pass(monkeypatch, ["blocked"])

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert lte.recorded[0][2] == "100"


async def test_a_log_that_cannot_be_written_is_not_a_false_alarm(lte, monkeypatch):
    """
    The panel change has already landed by the time the note is written. If a
    failed note counted as a failed reconciliation it would report a user as
    unenforced when they were enforced fine -- and failures are now the only
    thing that still interrupts anybody, so it would be a false alarm with
    nothing beside it to give it context.
    """
    _one_user_pass(monkeypatch, ["blocked"])

    async def boom(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(subscription_expire_monitor._enforcement, "record", boom)

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert lte.messages == []


async def test_the_recut_of_a_drifting_node_is_visible_in_the_daily_count(
    lte, monkeypatch
):
    """
    It never had a message of its own -- `_run` counts blocks and unblocks and
    nothing else -- so before this it was in the logs or nowhere. It is the
    one outcome that means the node disagreed with the panel, which is worth
    noticing across days rather than one pass at a time.
    """
    _one_user_pass(monkeypatch, ["recut"])

    await lte_traffic_monitor.run_lte_traffic_monitor()

    assert [action for _job, action, _subject in lte.recorded] == ["recut"]

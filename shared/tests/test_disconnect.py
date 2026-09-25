"""
Ending a live session so that it stays ended.

Two things have to happen and neither is sufficient alone. A node is told what
a user may reach only when the panel pushes it, and taking somebody out of a
squad is recorded *without* being pushed -- measured against a live client, the
session ran on for two minutes after the block. `/connections/drop` destroys
the socket, but the client is still listed in the node's inbound and
reconnected inside five seconds. Disabling the account is what removes it from
every inbound; the drop is what ends the tunnel already up.

So: disable, drop, check the sockets are gone, enable. The enable re-pushes
whatever squads the user holds at that moment, which is why the caller has to
apply the membership change first -- see `admin_bot/tests/test_block_ordering`.

The unguarded half is the one worth testing hardest: if `enable` does not land
after `disable` did, the account has no access at all and nothing puts it back.
"""

import pytest
from tgvpn_shared.remnawave import RemnawaveClient, UserLeftDisabledError
from tgvpn_shared.remnawave import client as client_module
from tgvpn_shared.remnawave.client import _pending_enable
from tgvpn_shared.remnawave.errors import APINotFoundError, APIServerError

# Captured before the fixture below zeroes it, so the one test that cares about
# the real duration still sees it.
REAL_HOLD_SECONDS = client_module._DISABLE_HOLD_SECONDS

NODE_A = "11111111-1111-1111-1111-111111111111"
NODE_B = "22222222-2222-2222-2222-222222222222"


def connected(*node_uuids: str, ip: str = "203.0.113.9") -> list[dict]:
    """What the panel reports for a user holding a session on those nodes."""
    return [{"nodeUuid": uuid, "ips": [{"ip": ip}]} for uuid in node_uuids]


@pytest.fixture(autouse=True)
def _no_leftovers(monkeypatch):
    """The pending set is module state; one test must not seed the next."""
    # The waits are seconds by design. Paying them in every test here would
    # make this the slowest file in the suite and prove nothing the constants
    # do not already say.
    monkeypatch.setattr(client_module, "_DISABLE_HOLD_SECONDS", 0)
    monkeypatch.setattr(client_module, "_DROP_VERIFY_DELAYS", (0, 0, 0, 0))
    monkeypatch.setattr(client_module, "_CONNECTION_JOB_INTERVAL", 0)
    _pending_enable.clear()
    yield
    _pending_enable.clear()


class FakePanel(RemnawaveClient):
    """A client whose HTTP layer is a script of what the panel answers."""

    def __init__(self, *, answers=None, fail_enable=0, live=None, survives_drops=0):
        super().__init__(base_url="https://panel.test.invalid", token="t")
        # (method, endpoint) -> exception to raise, if any
        self.answers = answers or {}
        self.fail_enable = fail_enable
        # Sessions the user currently holds, and how many drops they outlive.
        self.live = list(live or [])
        self.survives_drops = survives_drops
        self.drops = 0
        self.calls: list[tuple[str, str]] = []
        self.bodies: dict[str, dict] = {}

    async def request(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint))
        if kwargs.get("json"):
            self.bodies[endpoint] = kwargs["json"]
        if "enable" in endpoint and self.fail_enable:
            self.fail_enable -= 1
            raise APIServerError("panel unreachable")
        error = self.answers.get((method, endpoint))
        if error:
            raise error

        if endpoint == "/connections/drop":
            self.drops += 1
            if self.drops > self.survives_drops:
                self.live = []
            return {"response": {}}
        if endpoint.startswith("/connections/by-user/"):
            if method == "POST":
                return {"response": {"jobId": "job-1"}}
            return {"response": {"isCompleted": True, "result": {"nodes": self.live}}}
        return {"response": {}}

    @property
    def endpoints(self) -> list[str]:
        return [endpoint for _, endpoint in self.calls]

    @property
    def drop_body(self) -> dict:
        return self.bodies["/connections/drop"]


def no_connections_module() -> dict:
    """An older panel: the module the real lever lives in does not exist."""
    return {
        ("POST", "/connections/drop"): APINotFoundError("Cannot POST"),
        ("POST", "/connections/by-user/104"): APINotFoundError("Cannot POST"),
    }


# -- the shape of a cut ----------------------------------------------------


async def test_the_account_is_shut_out_before_the_sockets_are_destroyed():
    """
    Dropping first is what the previous version did, and it is why a blocked
    user kept browsing: the socket died and the client, still listed in the
    node's inbound, was back inside five seconds.
    """
    panel = FakePanel(live=connected(NODE_A))

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints[0] == "/users/104/actions/disable"
    assert "/connections/drop" in panel.endpoints
    assert panel.endpoints[-1] == "/users/104/actions/enable"


async def test_the_account_comes_back_last_so_the_node_is_re_pushed():
    """
    `enable` is what makes the panel hand the node the user's squads again.
    Nothing may run after it, or the node ends up holding something staler
    than what the caller decided.
    """
    panel = FakePanel()
    await panel.disconnect_user("104")
    assert panel.endpoints[-1] == "/users/104/actions/enable"


async def test_an_older_spelling_is_tried_when_the_newest_is_absent():
    answers = {("POST", "/users/104/actions/disable"): APINotFoundError("Cannot POST")}
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints[0:2] == ["/users/104/actions/disable", "/users/disable/104"]
    assert panel.endpoints[-1] == "/users/enable/104"


async def test_a_panel_offering_nothing_reports_failure_rather_than_raising():
    """
    A demotion that lands but cannot drop the session is still worth keeping,
    so this returns False instead of aborting the caller's pass.
    """
    answers = no_connections_module()
    for ref in ("/users/104/actions/disable", "/users/disable/104", "/users/104/disable"):
        answers[("POST", ref)] = APINotFoundError("no")
        answers[("PATCH", ref)] = APINotFoundError("no")
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is False
    assert not _pending_enable


# -- 202 is not a result ---------------------------------------------------
#
# `/connections/drop` answers the instant the panel has queued the work. That
# proves the panel accepted the instruction, never that a socket died.


async def test_a_session_that_survives_the_drop_is_dropped_again():
    panel = FakePanel(live=connected(NODE_A), survives_drops=2)

    assert await panel.disconnect_user("104") is True
    assert panel.drops == 3


async def test_a_session_that_never_dies_is_reported_rather_than_hidden():
    """False, and the account still comes back: a stuck socket is not a reason
    to leave a customer with no access at all."""
    panel = FakePanel(live=connected(NODE_A), survives_drops=99)

    assert await panel.disconnect_user("104") is False
    assert panel.endpoints[-1] == "/users/104/actions/enable"
    assert not _pending_enable


async def test_a_session_on_a_node_we_did_not_drop_does_not_count():
    """
    A quota is spent on the metered nodes. Someone still connected to an
    ordinary server has not survived anything -- reading that as a failed drop
    would retry forever and then report a cut that worked as broken.
    """
    panel = FakePanel(live=connected(NODE_B), survives_drops=99)

    assert await panel.disconnect_user("104", node_uuids=[NODE_A]) is True
    assert panel.drops == 1


async def test_a_panel_that_cannot_say_is_waited_out_not_believed():
    """
    "I don't know" is not "nobody is connected". The drop was accepted, so the
    account is held out for the hold instead, and the caller is told it ran.
    """
    panel = FakePanel(answers={("POST", "/connections/by-user/104"): APINotFoundError("no")})

    assert await panel.disconnect_user("104") is True
    assert panel.drops == 1


# -- what actually goes on the wire ----------------------------------------


async def test_only_the_named_nodes_are_dropped():
    """
    A traffic quota is spent on metered nodes. Someone who exhausts it should
    lose those and keep the ordinary servers their subscription still covers.
    """
    panel = FakePanel()
    await panel.disconnect_user("104", node_uuids=[NODE_A, NODE_B])

    assert panel.drop_body["dropBy"] == {"by": "userIds", "userIds": [104]}
    assert panel.drop_body["targetNodes"] == {
        "target": "specificNodes",
        "nodeUuids": [NODE_A, NODE_B],
    }


async def test_no_named_nodes_means_every_node():
    """What a demotion wants: the subscription has lapsed everywhere."""
    panel = FakePanel()
    await panel.disconnect_user("104")
    assert panel.drop_body["targetNodes"] == {"target": "allNodes"}


async def test_a_uuid_named_panel_skips_the_module_entirely():
    """
    The contract types `userIds` as numbers. A panel that names users by UUID
    is an older generation with no such module, and asking costs a round trip
    to be told so.
    """
    panel = FakePanel()
    assert await panel.disconnect_user("abc-uuid") is False
    assert "/connections/drop" not in panel.endpoints
    assert panel.endpoints == ["/users/abc-uuid/actions/disable", "/users/abc-uuid/actions/enable"]


async def test_an_older_panel_holds_the_account_out_instead():
    """
    Nothing here can destroy a socket, so the only lever left is time. The cut
    is reported as not having run, because it did not.
    """
    panel = FakePanel(answers=no_connections_module())

    assert await panel.disconnect_user("104") is False
    assert panel.endpoints == [
        "/users/104/actions/disable",
        "/connections/drop",  # asked once, told no; nothing else to try
        "/users/104/actions/enable",
    ]


async def test_the_hold_is_seconds_not_milliseconds(monkeypatch):
    """
    Node and panel are eventually consistent: a removal and an addition
    delivered together are applied as their sum, which is nothing. The first
    version flipped in 61 milliseconds and changed nothing observable.
    """
    assert REAL_HOLD_SECONDS >= 1


# -- the failure that matters ----------------------------------------------


async def test_a_transient_failure_is_retried_rather_than_abandoned():
    """Two refusals then success: the account ends up enabled, nothing stuck."""
    panel = FakePanel(fail_enable=2)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints.count("/users/104/actions/enable") == 3
    assert not _pending_enable


async def test_an_account_left_disabled_raises_its_own_error():
    """
    Not an ordinary per-user failure: this one means no access at all, and the
    caller alerts on it specifically.
    """
    panel = FakePanel(fail_enable=99)

    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")


async def test_an_account_left_disabled_is_remembered_for_the_next_pass():
    panel = FakePanel(fail_enable=99)
    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")

    assert _pending_enable == {"104"}


async def test_the_account_is_put_back_even_when_the_drop_blows_up():
    """
    The drop is best-effort; leaving somebody disabled is not. An exception on
    the way through must not skip the half that restores access.
    """
    panel = FakePanel(answers={("POST", "/connections/drop"): RuntimeError("node exploded")})

    with pytest.raises(RuntimeError):
        await panel.disconnect_user("104")
    assert panel.endpoints[-1] == "/users/104/actions/enable"


async def test_already_enabled_is_agreement_not_failure():
    """
    The panel refuses to enable an account that is already enabled -- with a
    400, same shape as a real error. Retrying that would burn four calls and
    then declare a working account stuck.
    """
    answers = {
        ("POST", "/users/104/actions/enable"): APIServerError(
            "User already enabled (status: 400)"
        )
    }
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints.count("/users/104/actions/enable") == 1
    assert not _pending_enable


# -- recovery --------------------------------------------------------------


async def test_a_stuck_account_is_put_back_on_the_next_pass():
    panel = FakePanel(fail_enable=99)
    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")

    healthy = FakePanel()
    assert await healthy.flush_pending_enables() == []
    assert not _pending_enable
    assert healthy.endpoints == ["/users/104/actions/enable"]


async def test_an_account_still_unreachable_is_reported_not_forgotten():
    panel = FakePanel(fail_enable=99)
    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")

    still_broken = FakePanel(fail_enable=99)
    assert await still_broken.flush_pending_enables() == ["104"]
    assert _pending_enable == {"104"}


async def test_nothing_pending_costs_no_call():
    """Runs on every monitor pass; a quiet deployment must not pay for it."""
    panel = FakePanel()
    assert await panel.flush_pending_enables() == []
    assert panel.calls == []


async def test_only_accounts_we_disabled_are_ever_enabled():
    """
    An operator who disables somebody in the panel by hand must not have it
    silently undone. Nothing is enabled that this process did not disable.
    """
    panel = FakePanel()
    await panel.flush_pending_enables()
    assert panel.endpoints == []


# -- asking who is connected -----------------------------------------------


async def test_the_query_is_a_job_polled_by_the_id_it_hands_back():
    """
    Both halves are spelled `by-user`, which reads like a mistake and is not:
    the GET's path parameter is the job, not the user.
    """
    panel = FakePanel(live=connected(NODE_A, ip="198.51.100.7"))

    assert await panel.active_connections("104") == ["198.51.100.7"]
    assert panel.endpoints == ["/connections/by-user/104", "/connections/by-user/job-1"]


async def test_not_knowing_is_reported_as_not_knowing():
    """None, not []. The caller decides what to do about an unanswerable
    question, and must not read it as "nobody is connected"."""
    panel = FakePanel(answers={("POST", "/connections/by-user/104"): APINotFoundError("no")})
    assert await panel.active_connections("104") is None


async def test_a_uuid_named_panel_is_not_asked_at_all():
    panel = FakePanel()
    assert await panel.active_connections("abc-uuid") is None
    assert panel.calls == []

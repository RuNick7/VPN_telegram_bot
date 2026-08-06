"""
Dropping a live session.

Removing someone from a squad stops *new* connections and leaves the tunnel
they already hold running, so a user over their traffic quota kept browsing
after being blocked. Current Remnawave has no per-user disconnect at all --
every spelling 404s and its own API exposes none -- so the only lever short of
restarting the node's xray, which would drop everybody on it, is to disable the
account for an instant and enable it straight back.

`legacy-main` had that fallback and the Phase 2 refactor dropped it. It also
shipped it unguarded, which is the part worth testing: if `enable` does not
land after `disable` did, the account has no access at all and nothing puts it
back.
"""

import pytest
from tgvpn_shared.remnawave import RemnawaveClient, UserLeftDisabledError
from tgvpn_shared.remnawave import client as client_module
from tgvpn_shared.remnawave.client import _pending_enable
from tgvpn_shared.remnawave.errors import APINotFoundError, APIServerError

# Captured before the fixture below zeroes it, so the one test that cares about
# the real duration still sees it.
REAL_HOLD_SECONDS = client_module._DISABLE_HOLD_SECONDS


@pytest.fixture(autouse=True)
def _no_leftovers(monkeypatch):
    """The pending set is module state; one test must not seed the next."""
    # The hold is seconds by design. Paying it in every test here would make
    # this the slowest file in the suite and prove nothing the constant does
    # not already say.
    monkeypatch.setattr(client_module, "_DISABLE_HOLD_SECONDS", 0)
    _pending_enable.clear()
    yield
    _pending_enable.clear()


class FakePanel(RemnawaveClient):
    """A client whose HTTP layer is a script of what the panel answers."""

    def __init__(self, *, answers=None, fail_enable=0):
        super().__init__(base_url="https://panel.test.invalid", token="t")
        # (method, endpoint) -> exception to raise, if any
        self.answers = answers or {}
        self.fail_enable = fail_enable
        self.calls: list[tuple[str, str]] = []

    async def request(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint))
        if "enable" in endpoint and self.fail_enable:
            self.fail_enable -= 1
            raise APIServerError("panel unreachable")
        error = self.answers.get((method, endpoint))
        if error:
            raise error
        return {"response": {}}

    @property
    def endpoints(self) -> list[str]:
        return [endpoint for _, endpoint in self.calls]


def no_disconnect_endpoints() -> dict:
    """What the live panel answers: none of the disconnect spellings exist."""
    return {
        ("POST", "/users/104/actions/disconnect"): APINotFoundError("Cannot POST"),
        ("POST", "/users/104/disconnect"): APINotFoundError("Cannot POST"),
        ("POST", "/users/disconnect/104"): APINotFoundError("Cannot POST"),
        ("POST", "/users/bulk/disconnect"): APINotFoundError("Cannot POST"),
    }


# -- the happy path --------------------------------------------------------


async def test_a_panel_with_a_disconnect_endpoint_is_left_alone():
    """The flip is a fallback; an account is not disabled when it is avoidable."""
    panel = FakePanel()
    assert await panel.disconnect_user("104") is True
    assert panel.endpoints == ["/users/104/actions/disconnect"]


async def test_the_flip_runs_when_no_disconnect_endpoint_exists():
    panel = FakePanel(answers=no_disconnect_endpoints())
    assert await panel.disconnect_user("104") is True
    assert panel.endpoints[-2:] == [
        "/users/104/actions/disable",
        "/users/104/actions/enable",
    ]


async def test_an_older_spelling_is_tried_when_the_newest_is_absent():
    answers = no_disconnect_endpoints()
    answers[("POST", "/users/104/actions/disable")] = APINotFoundError("Cannot POST")
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints[-2:] == ["/users/disable/104", "/users/enable/104"]


async def test_a_panel_offering_nothing_reports_failure_rather_than_raising():
    """
    A demotion that lands but cannot drop the session is still worth keeping,
    so this returns False instead of aborting the caller's pass.
    """
    answers = no_disconnect_endpoints()
    for ref in ("/users/104/actions/disable", "/users/disable/104", "/users/104/disable"):
        answers[("POST", ref)] = APINotFoundError("no")
        answers[("PATCH", ref)] = APINotFoundError("no")
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is False
    assert not _pending_enable


# -- the failure that matters ----------------------------------------------


async def test_a_transient_failure_is_retried_rather_than_abandoned():
    """Two refusals then success: the account ends up enabled, nothing stuck."""
    panel = FakePanel(answers=no_disconnect_endpoints(), fail_enable=2)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints.count("/users/104/actions/enable") == 3
    assert not _pending_enable


async def test_an_account_left_disabled_raises_its_own_error():
    """
    Not an ordinary per-user failure: this one means no access at all, and the
    caller alerts on it specifically.
    """
    panel = FakePanel(answers=no_disconnect_endpoints(), fail_enable=99)

    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")


async def test_an_account_left_disabled_is_remembered_for_the_next_pass():
    panel = FakePanel(answers=no_disconnect_endpoints(), fail_enable=99)
    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")

    assert _pending_enable == {"104"}


async def test_already_enabled_is_agreement_not_failure():
    """
    The panel refuses to enable an account that is already enabled -- with a
    400, same shape as a real error. Retrying that would burn four calls and
    then declare a working account stuck.
    """
    answers = no_disconnect_endpoints()
    answers[("POST", "/users/104/actions/enable")] = APIServerError(
        "User already enabled (status: 400)"
    )
    panel = FakePanel(answers=answers)

    assert await panel.disconnect_user("104") is True
    assert panel.endpoints.count("/users/104/actions/enable") == 1
    assert not _pending_enable


# -- recovery --------------------------------------------------------------


async def test_a_stuck_account_is_put_back_on_the_next_pass():
    panel = FakePanel(answers=no_disconnect_endpoints(), fail_enable=99)
    with pytest.raises(UserLeftDisabledError):
        await panel.disconnect_user("104")

    healthy = FakePanel()
    assert await healthy.flush_pending_enables() == []
    assert not _pending_enable
    assert healthy.endpoints == ["/users/104/actions/enable"]


async def test_an_account_still_unreachable_is_reported_not_forgotten():
    panel = FakePanel(answers=no_disconnect_endpoints(), fail_enable=99)
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

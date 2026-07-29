"""Internal-squad placement arithmetic (no panel, no database)."""

import pytest

from tgvpn_shared.squads import (
    extract_inbound_ids,
    get_or_create_internal_squad,
    members_count,
    next_internal_squad_name,
)


def test_members_count_defaults_to_zero_when_absent():
    assert members_count({}) == 0
    assert members_count({"info": {}}) == 0
    assert members_count({"info": {"membersCount": None}}) == 0
    assert members_count({"info": {"membersCount": 7}}) == 7


def test_extract_inbound_ids_skips_entries_without_uuid():
    squad = {"inbounds": [{"uuid": "a"}, {}, {"uuid": "b"}]}
    assert extract_inbound_ids(squad) == ["a", "b"]
    assert extract_inbound_ids(None) == []
    assert extract_inbound_ids({}) == []


@pytest.mark.parametrize(
    "names, expected",
    [
        ([], "internal-1"),
        (["internal-1"], "internal-2"),
        # Numbering continues from the highest, not the count -- a deleted
        # squad in the middle must not cause a name collision.
        (["internal-1", "internal-3"], "internal-4"),
        (["internal-abc", "other-9"], "internal-1"),
        (["internal-10", "internal-9"], "internal-11"),
    ],
)
def test_next_internal_squad_name(names, expected):
    squads = [{"name": name} for name in names]
    assert next_internal_squad_name("internal", squads) == expected


class FakeClient:
    """Records squad creation so placement decisions can be asserted."""

    def __init__(self, squads):
        self._squads = squads
        self.created: list[tuple[str, list[str]]] = []

    async def list_internal_squads(self):
        return self._squads

    async def create_internal_squad(self, name, inbound_ids):
        self.created.append((name, inbound_ids))
        return {"uuid": f"uuid-{name}", "name": name}


async def test_reuses_the_first_squad_with_room():
    client = FakeClient(
        [
            {"uuid": "full", "name": "internal-1", "info": {"membersCount": 30}},
            {"uuid": "roomy", "name": "internal-2", "info": {"membersCount": 5}},
        ]
    )
    squad, created = await get_or_create_internal_squad(client, max_users=30, prefix="internal")

    assert squad["uuid"] == "roomy"
    assert created is False
    assert client.created == []


async def test_creates_the_next_squad_when_all_are_full():
    client = FakeClient(
        [
            {
                "uuid": "s1",
                "name": "internal-1",
                "info": {"membersCount": 30},
                "inbounds": [{"uuid": "in-1"}, {"uuid": "in-2"}],
            },
        ]
    )
    squad, created = await get_or_create_internal_squad(client, max_users=30, prefix="internal")

    assert created is True
    assert squad["name"] == "internal-2"
    # The new squad copies inbounds from an existing one, so it carries the
    # same connectivity instead of coming up empty.
    assert client.created == [("internal-2", ["in-1", "in-2"])]


async def test_creates_the_first_squad_when_none_exist():
    client = FakeClient([])
    squad, created = await get_or_create_internal_squad(client, max_users=30, prefix="internal")

    assert created is True
    assert squad["name"] == "internal-1"
    assert client.created == [("internal-1", [])]


async def test_a_squad_exactly_at_the_cap_is_treated_as_full():
    client = FakeClient([{"uuid": "s1", "name": "internal-1", "info": {"membersCount": 30}}])
    _, created = await get_or_create_internal_squad(client, max_users=30, prefix="internal")
    assert created is True

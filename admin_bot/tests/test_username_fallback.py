"""
Looking a panel user up by name, when the direct endpoint finds nobody.

The direct endpoint matches on username alone. The full scan behind it also
matches on telegramId, which is how a user whose panel username was changed
away from their Telegram ID is still found -- and why skipping the scan made
inactive-user cleanup pass over accounts that were really there.
"""

from app.services.users import UserService
from tgvpn_shared.remnawave import UserNotFoundError

USER = {"uuid": "3f2504e0-4f89-41d3-9a0c-0305e82c3301", "username": "renamed", "telegramId": 123456789}


class Client:
    def __init__(self, direct):
        self.direct = direct
        self.scanned = False

    async def get_user_by_username(self, username):
        if isinstance(self.direct, Exception):
            raise self.direct
        return self.direct

    async def iter_all_users(self):
        self.scanned = True
        yield {"uuid": "someone-else", "username": "other", "telegramId": 1}
        yield USER


def service_with(client) -> UserService:
    service = UserService()
    service.client = client
    return service


async def test_nobody_found_directly_falls_through_to_the_scan():
    client = Client(UserNotFoundError("User not found: 123456789"))

    assert await service_with(client).get_user_by_username("123456789") == USER
    assert client.scanned


async def test_a_direct_hit_does_not_scan_the_whole_panel():
    client = Client(USER)

    assert await service_with(client).get_user_by_username("renamed") == USER
    assert not client.scanned


async def test_a_failing_direct_lookup_still_scans():
    client = Client(RuntimeError("502 Bad Gateway"))

    assert await service_with(client).get_user_by_username("123456789") == USER


async def test_nobody_anywhere_is_an_empty_answer():
    client = Client(UserNotFoundError("User not found: 555"))

    assert await service_with(client).get_user_by_username("555") == {}

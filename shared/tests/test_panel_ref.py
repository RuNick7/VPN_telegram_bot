"""
Panel identifiers across two generations of Remnawave.

Older panels give every user a `uuid`; newer ones dropped it and address users
by a numeric `id`, which also changed the key several request bodies expect.
Getting this wrong is not cosmetic: the client reported every existing account
as missing, created it again, and was told the name was taken -- on every
request. A customer paid, YooKassa confirmed, and nothing was credited.

These mirror `internal/panel/ref_test.go` on the Go side. The bot and the
website create accounts for the same people and must agree.
"""

import pytest
from tgvpn_shared.remnawave.client import identify, is_numeric_ref, panel_ref


class TestPanelRef:
    def test_an_older_panel_gives_a_uuid(self):
        user = {"uuid": "c2400d02-06a0-4b21-a310-d1a888a088bb", "username": "u-abc"}
        assert panel_ref(user) == "c2400d02-06a0-4b21-a310-d1a888a088bb"

    def test_a_newer_panel_gives_a_numeric_id_and_no_uuid_at_all(self):
        user = {"id": 2, "username": "u-abc", "shortUuid": "SayZcYcdx7zRHfxe"}
        assert panel_ref(user) == "2"

    def test_the_uuid_wins_when_a_panel_serves_both(self):
        """
        It is the stabler handle, and it is what rows written before the
        version change already contain.
        """
        user = {"uuid": "c2400d02-06a0-4b21-a310-d1a888a088bb", "id": 2}
        assert panel_ref(user) == "c2400d02-06a0-4b21-a310-d1a888a088bb"

    @pytest.mark.parametrize("value", [{}, {"username": "u-abc"}, {"uuid": ""}, None, "nope", 5])
    def test_nothing_usable_yields_nothing(self, value):
        """
        Empty means "we cannot act on this account". The caller must be able to
        see that rather than passing an empty string into a URL path.
        """
        assert panel_ref(value) == ""


class TestNumericRef:
    def test_a_uuid_is_not_mistaken_for_an_id(self):
        # This is the whole basis for storing one string and working out later
        # which panel produced it, so it has to be exact.
        assert not is_numeric_ref("c2400d02-06a0-4b21-a310-d1a888a088bb")
        assert not is_numeric_ref("2f")
        assert not is_numeric_ref("")
        assert not is_numeric_ref("  ")

    def test_an_id_is(self):
        assert is_numeric_ref("2")
        assert is_numeric_ref(2)
        assert is_numeric_ref(" 46 ")


class TestIdentify:
    def test_a_numeric_ref_is_sent_as_a_number_under_id(self):
        """
        The newer panel answers "At least one of username, id must be provided"
        and rejects a quoted id. Right key with the wrong JSON type is still a
        400.
        """
        body = identify("46")
        assert body == {"id": 46}
        assert isinstance(body["id"], int)

    def test_a_uuid_ref_is_sent_as_a_string_under_uuid(self):
        body = identify("c2400d02-06a0-4b21-a310-d1a888a088bb")
        assert body == {"uuid": "c2400d02-06a0-4b21-a310-d1a888a088bb"}

    def test_only_one_key_is_ever_sent(self):
        # Sending both would have the panel pick, and the two could disagree.
        assert set(identify("46")) == {"id"}
        assert set(identify("c2400d02-06a0-4b21-a310-d1a888a088bb")) == {"uuid"}

"""What is left of squad handling once distribution is gone."""

from tgvpn_shared.squads import members_count


def test_members_count_defaults_to_zero_when_absent():
    """
    The panel omits the count on some versions. Zero rather than an error
    because the only consumer is a daily headcount report -- a missing number
    should read as "nothing to say", not take the report down.
    """
    assert members_count({}) == 0
    assert members_count({"info": {}}) == 0
    assert members_count({"info": {"membersCount": None}}) == 0
    assert members_count({"info": {"membersCount": 7}}) == 7


def test_members_count_ignores_a_non_integer():
    assert members_count({"info": {"membersCount": "many"}}) == 0

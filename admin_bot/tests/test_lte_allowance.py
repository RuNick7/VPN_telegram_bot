"""Per-user free allowance resolution."""

from tgvpn_shared.lte_quota import free_bytes_for

GB = 1024**3
GLOBAL_GB = 10


def test_no_override_uses_the_global_setting():
    assert free_bytes_for({"lte_free_gb_override": None}, GLOBAL_GB) == 10 * GB


def test_missing_key_uses_the_global_setting():
    """A state dict from an older query shape must not crash the monitor."""
    assert free_bytes_for({}, GLOBAL_GB) == 10 * GB


def test_an_override_wins_over_the_global_setting():
    assert free_bytes_for({"lte_free_gb_override": 50}, GLOBAL_GB) == 50 * GB


def test_a_zero_override_means_no_free_traffic():
    """
    The case that makes `is None` the right check rather than falsiness: 0 is
    a deliberate override, not an absent one.
    """
    assert free_bytes_for({"lte_free_gb_override": 0}, GLOBAL_GB) == 0


def test_an_override_below_the_global_is_honoured():
    assert free_bytes_for({"lte_free_gb_override": 1}, GLOBAL_GB) == 1 * GB


def test_a_negative_override_is_clamped_to_zero():
    assert free_bytes_for({"lte_free_gb_override": -5}, GLOBAL_GB) == 0

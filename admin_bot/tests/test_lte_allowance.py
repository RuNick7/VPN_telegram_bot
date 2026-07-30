"""Per-user free allowance resolution."""

import pytest

from app.scheduler.jobs.lte_traffic_monitor import free_bytes_for

GB = 1024**3


@pytest.fixture
def global_allowance_10gb(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "lte_free_gb_per_cycle", 10)


def test_no_override_uses_the_global_setting(global_allowance_10gb):
    assert free_bytes_for({"lte_free_gb_override": None}) == 10 * GB


def test_missing_key_uses_the_global_setting(global_allowance_10gb):
    """A state dict from an older query shape must not crash the monitor."""
    assert free_bytes_for({}) == 10 * GB


def test_an_override_wins_over_the_global_setting(global_allowance_10gb):
    assert free_bytes_for({"lte_free_gb_override": 50}) == 50 * GB


def test_a_zero_override_means_no_free_traffic(global_allowance_10gb):
    """
    The case that makes `is None` the right check rather than falsiness: 0 is
    a deliberate override, not an absent one.
    """
    assert free_bytes_for({"lte_free_gb_override": 0}) == 0


def test_an_override_below_the_global_is_honoured(global_allowance_10gb):
    assert free_bytes_for({"lte_free_gb_override": 1}) == 1 * GB

"""
LTE quota arithmetic: cycle windows and what a monitor pass costs.

Pure functions, no I/O. They live in `shared/` rather than beside the monitor
that drives them because this is domain logic about traffic accounting, not
something specific to admin_bot -- and keeping it importable from the shared
test suite is what lets the carry-over guarantee be tested end to end (the two
bots cannot be collected in one pytest process).
"""

from __future__ import annotations

BYTES_PER_GB = 1024**3
BYTES_PER_MB = 1024**2

# Warn at these remaining amounts, in megabytes, tightest last. Two levels so
# a user gets a heads-up with room to act and a final warning right before
# metered access stops.
LOW_TRAFFIC_THRESHOLDS_MB = (500, 150)


def remaining_bytes(*, usage_bytes: int, free_bytes: int, paid_balance: int) -> int:
    """What the user still has to spend: unused allowance plus bought traffic."""
    return max(0, free_bytes - usage_bytes) + max(0, paid_balance)


def low_traffic_threshold(
    remaining: int, thresholds_mb: tuple[int, ...] = LOW_TRAFFIC_THRESHOLDS_MB
) -> int:
    """
    The tightest warning level this much remaining has crossed, or 0.

    Returning the level rather than a boolean is what lets the caller tell
    "already warned at 500" from "now down to 150" and send the second warning
    without repeating the first.
    """
    crossed = [mb for mb in thresholds_mb if remaining <= mb * BYTES_PER_MB]
    return min(crossed) if crossed else 0


def free_bytes_for(state: dict, global_free_gb: int) -> int:
    """
    This user's free allowance per cycle, in bytes.

    A per-user override wins over the global setting. `None` means no
    override; `0` is a real one meaning no free traffic at all, which is why
    this checks for None rather than falsiness.
    """
    override = state.get("lte_free_gb_override")
    if override is None:
        return max(0, global_free_gb) * BYTES_PER_GB
    return max(0, int(override)) * BYTES_PER_GB


def settle_cycle(
    *,
    now: int,
    cycle_start: int,
    cycle_seconds: int,
    cycle_spent: int,
) -> tuple[int, int]:
    """
    Advance the quota window past every elapsed cycle.

    Returns `(cycle_start, cycle_spent)`. Whole cycles are skipped in one step
    rather than one per pass, so a user the monitor hasn't seen in months
    lands on the correct current window immediately.

    Spend within the window resets. The purchased balance deliberately does
    not -- and is not even touched here -- because bought traffic belongs to
    the user rather than to a cycle.
    """
    if cycle_seconds <= 0:
        return cycle_start, cycle_spent
    elapsed_cycles = (now - cycle_start) // cycle_seconds
    if elapsed_cycles <= 0:
        return cycle_start, cycle_spent
    return cycle_start + elapsed_cycles * cycle_seconds, 0


def plan_quota(
    *,
    usage_bytes: int,
    free_bytes: int,
    cycle_spent: int,
    paid_balance: int,
    subscription_active: bool,
) -> tuple[int, int, bool]:
    """
    Work out what this pass costs. Returns `(spend_delta, cycle_spent, blocked)`.

    Usage above the free allowance is charged to purchased traffic. Only the
    amount *newly* charged is returned as `spend_delta` -- the caller
    subtracts exactly that from the live balance, never a recomputed total.
    That is what keeps a purchase landing mid-pass from being erased.

    A lapsed subscription blocks regardless of remaining balance: free mode
    means free servers, and metered ones are not among them.
    """
    over_free = max(0, usage_bytes - free_bytes)
    newly_charged = max(0, min(over_free - cycle_spent, paid_balance))
    cycle_spent_after = cycle_spent + newly_charged
    unpaid = max(0, over_free - cycle_spent_after)
    return newly_charged, cycle_spent_after, bool(unpaid > 0 or not subscription_active)

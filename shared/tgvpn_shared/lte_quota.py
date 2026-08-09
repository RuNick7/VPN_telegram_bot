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
BYTES_PER_KB = 1024

# Warn at these remaining amounts, in megabytes, tightest last. Two levels so
# a user gets a heads-up with room to act and a final warning right before
# metered access stops.
LOW_TRAFFIC_THRESHOLDS_MB = (500, 150)

# What the metered squad is called anywhere a customer can see it.
#
# "LTE" is an internal name. It tells a user nothing about what they are
# buying and reads as the mobile standard of the same name, which this is not.
# Identifiers keep the old spelling on purpose -- columns, env vars, callback
# data and module names are all `lte_*`, and renaming them costs a migration
# plus an .env edit on every deployment while changing nothing a user sees.
#
# Only this exact phrase is shared. Russian declension does not compose from
# constants, so genitive forms ("на серверах белых списков") stay written out
# at the few places that need them.
TRAFFIC_LABEL = "Трафик белых списков"

# The callback that opens the traffic packs.
#
# Shared because it crosses a process boundary: user_bot registers the
# handler, and admin_bot's traffic monitor puts the button on the warnings it
# sends *through user_bot's token*. A literal on each side would be a contract
# nothing checks, and a button that answers nothing looks to a customer like a
# broken bot rather than a typo.
TRAFFIC_TOPUP_CALLBACK = "lte_packs"


def format_traffic(byte_count: int) -> str:
    """
    Bytes as an amount a customer reads at a glance: '4.7 ГБ', '350 МБ', '120 КБ'.

    Kilobytes are worth the extra branch. Rounding everything below a megabyte
    to "0 МБ" makes a meter that works look exactly like one that does not --
    which is how a metering bug here stayed invisible while the panel had the
    figure all along.

    Zero keeps the megabyte spelling: it is an empty balance, not a very small
    one, and "0 КБ" reads like a rounding artefact.
    """
    byte_count = max(0, int(byte_count))
    if byte_count >= BYTES_PER_GB:
        return f"{byte_count / BYTES_PER_GB:.1f} ГБ"
    if byte_count >= BYTES_PER_MB or byte_count == 0:
        return f"{byte_count / BYTES_PER_MB:.0f} МБ"
    return f"{byte_count / BYTES_PER_KB:.0f} КБ"


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


def remaining_now(
    *,
    state: dict,
    global_free_gb: int,
    cycle_seconds: int,
    now: int,
) -> int:
    """
    What a user has left right now, from stored state alone -- no panel call.

    This is what a menu can afford to show: the monitor's last reading, not a
    fresh one. It is therefore a few minutes stale by construction, which is
    fine for a balance and not fine for enforcement -- `plan_quota` stays the
    only thing that decides access.

    The one correction made here is for a rolled window. A usage reading only
    means anything inside the cycle it was taken in; once the window rolls the
    allowance is fresh and nothing has been measured against it yet. Without
    that, a menu opened after a rollover but before the monitor's next pass
    would show last cycle's exhausted balance against this cycle's allowance.
    """
    usage = max(0, int(state.get("lte_last_usage_bytes") or 0))
    cycle_start = int(state.get("lte_cycle_start") or 0)
    if cycle_start:
        rolled_start, _ = settle_cycle(
            now=now,
            cycle_start=cycle_start,
            cycle_seconds=cycle_seconds,
            cycle_spent=0,
        )
        if rolled_start != cycle_start:
            usage = 0

    return remaining_bytes(
        usage_bytes=usage,
        free_bytes=free_bytes_for(state, global_free_gb),
        paid_balance=max(0, int(state.get("lte_paid_balance_bytes") or 0)),
    )


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

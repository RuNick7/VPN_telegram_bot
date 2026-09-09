"""
Panel-side state for the FREE tier: `expireAt` handling and tier tagging.

Two problems this solves.

**`expireAt` must not stay in the past.** Demoting a lapsed user to the FREE
squad changes squad membership only. If their `expireAt` has already passed,
Remnawave treats the account as expired regardless of which squad it sits in,
so the FREE servers they are supposed to fall back to would not work either.
Users who renew get a far-future date written by the payment path, but users
who were *already* expired when the FREE tier was switched on never renew --
they are exactly the population the feature exists for, and they would get
nothing. So the demotion job pushes `expireAt` forward itself.

**The tier has to be visible in the panel.** An operator looking at Remnawave
should be able to tell a free user from a paying one without cross-referencing
our database. The `tag` field carries that, and is also what makes an
accidental mass-demotion greppable after the fact.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .settings import get_settings

SECONDS_IN_DAY = 86400

# How long the FREE tier keeps a lapsed user's panel account alive.
#
# Shared between `inactive_user_cleanup` (which deletes the panel account
# once a user has sat unpaid this long) and user_bot's main menu (which stops
# offering device-setup buttons at the same point, rather than routing a tap
# on one into the account service silently recreating a profile the cleanup
# job just removed). The two must agree, or a user could see "choose your
# device" for an account that is already gone.
FREE_TIER_GRACE_DAYS = 30

# Written into the panel user's `tag`. Prefixed so they are recognisable as
# ours and cannot collide with a tag an operator typed by hand.
TAG_PAID = "TIER_PAID"
TAG_FREE = "TIER_FREE"
MANAGED_TAGS = frozenset({TAG_PAID, TAG_FREE})

# Only rewrite `expireAt` when it is inside this window. Without the slack,
# every pass would rewrite every user's date; with it, a user already pushed
# forward is left alone until the date genuinely approaches.
_REFRESH_WHEN_CLOSER_THAN = 365 * SECONDS_IN_DAY


def panel_expire_timestamp(subscription_ends: int, *, now: int | None = None) -> int:
    """
    What to write into the panel's `expireAt`, given the real expiry date.

    Returns the real date when the FREE tier is off, so the panel keeps
    expiring accounts itself exactly as before. Returns a far-future
    placeholder when it is on, because expiry is then enforced entirely by
    `subscription_expire_monitor` moving users between squads -- which is why
    that job is watched by the health monitor.
    """
    settings = get_settings()
    if not settings.free_tier_enabled:
        return subscription_ends
    years = max(1, settings.free_tier_panel_expire_years)
    return (now or int(time.time())) + years * 365 * SECONDS_IN_DAY


def parse_panel_timestamp(value: str | None) -> int | None:
    """Epoch seconds from the panel's ISO-8601 `expireAt`, or None."""
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return None


def format_panel_timestamp(timestamp: int) -> str:
    """`expireAt` in the ISO-8601/`Z` form the panel API expects."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def needs_expire_push(current_expire_at: str | None, now: int) -> bool:
    """
    Whether this account's `expireAt` needs pushing into the far future.

    True for a date already past or approaching, and for a missing or
    unparseable one -- in every such case leaving it alone risks the panel
    expiring an account the FREE tier is meant to keep alive.
    """
    current = parse_panel_timestamp(current_expire_at)
    if current is None:
        return True
    return current < now + _REFRESH_WHEN_CLOSER_THAN


def tier_tag(tier: str) -> str:
    if tier not in ("paid", "free"):
        raise ValueError(f"Unknown tier: {tier!r}")
    return TAG_PAID if tier == "paid" else TAG_FREE


def needs_tag_update(current_tag: str | None, tier: str) -> bool:
    """
    Whether the panel tag should be rewritten.

    A tag an operator set by hand is left alone: only our own `TIER_*` tags
    are ever replaced, so tagging a user "vip" in the panel survives
    reconciliation instead of being overwritten every five minutes.
    """
    desired = tier_tag(tier)
    if current_tag == desired:
        return False
    return not current_tag or current_tag in MANAGED_TAGS


def plan_panel_update(
    *,
    user: dict,
    tier: str,
    now: int,
) -> dict | None:
    """
    The `expireAt`/`tag` changes this user needs, or None if already correct.

    Returning None for "nothing to do" is what keeps reconciliation quiet: on
    a five-minute interval across hundreds of users, re-sending unchanged
    fields would be most of the job's API traffic.
    """
    if not get_settings().free_tier_enabled:
        return None

    payload: dict = {}

    current_expire = user.get("expireAt") or user.get("expire_at")
    if needs_expire_push(current_expire, now):
        payload["expireAt"] = format_panel_timestamp(
            panel_expire_timestamp(0, now=now)
        )

    if needs_tag_update(user.get("tag"), tier):
        payload["tag"] = tier_tag(tier)

    return payload or None

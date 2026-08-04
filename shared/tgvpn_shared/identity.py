"""
Who a person is, independently of Telegram.

Two pure decisions live here, out of the way of the I/O that applies them:
what a user's panel handle should be, and what merging two accounts produces.
Both are worth testing without a database or a panel, and both are the kind of
arithmetic that is easy to get subtly wrong in a way nobody notices until a
customer has lost days they paid for.

The rest of the rework is plumbing: `UserRepository` gains id-based lookups,
`vpn_service` resolves the panel account by stored UUID instead of by
`str(telegram_id)`, and the webhook credits by `user_id`.
"""

from __future__ import annotations

from dataclasses import dataclass

SECONDS_IN_DAY = 86400

# Prefix for panel usernames we mint ourselves. Short, and obviously ours when
# an operator is scanning a list of accounts in Remnawave.
PANEL_USERNAME_PREFIX = "u-"


def panel_username_for(user_id: str) -> str:
    """
    The panel username for an account we are creating now.

    Derived from our own UUID rather than from a Telegram ID, so an account
    can exist -- and be paid for -- with no Telegram at all.

    Accounts created before this change are *not* renamed. They keep
    `str(telegram_id)`, and `resolve_panel_identity` below is what lets both
    kinds be addressed the same way afterwards.
    """
    compact = user_id.replace("-", "")
    return f"{PANEL_USERNAME_PREFIX}{compact[:16]}"


def legacy_panel_username(telegram_id: int | None) -> str | None:
    """What a pre-rework account is called in the panel, if it is one."""
    return None if telegram_id is None else str(telegram_id)


@dataclass(frozen=True)
class PanelLookup:
    """How to find a user's panel account, in the order worth trying."""

    uuid: str | None
    username: str | None
    legacy_username: str | None

    @property
    def can_be_found(self) -> bool:
        return bool(self.uuid or self.username or self.legacy_username)


def resolve_panel_identity(user: dict) -> PanelLookup:
    """
    Where to look for this user's panel account.

    Ordered by how much we trust each handle. The stored UUID is authoritative
    and survives an operator renaming the account by hand. The stored username
    is next. `str(telegram_id)` is last and exists only for accounts created
    before the rework, which is also why finding a user that way triggers a
    backfill of the first two -- each legacy lookup is one fewer forever.
    """
    return PanelLookup(
        uuid=(user.get("remnawave_uuid") or None) and str(user["remnawave_uuid"]),
        username=user.get("remnawave_username") or None,
        legacy_username=legacy_panel_username(user.get("telegram_id")),
    )


@dataclass(frozen=True)
class MergePlan:
    """
    What folding one account into another produces.

    `survivor_id` keeps existing; `absorbed_id` is marked as merged into it and
    stops being addressable on its own.
    """

    survivor_id: str
    absorbed_id: str
    subscription_ends: int
    lte_paid_balance_bytes: int
    gifted_subscriptions: int
    referred_people: int
    email: str | None
    referrer_tag: str | None
    # Whether the absorbed row has to give its address up.
    #
    # `users.email` is UNIQUE, so one address cannot sit on two rows at once.
    # The survivor adopting an address the absorbed row still holds is a
    # constraint violation, and that is precisely what it was: every link of a
    # website account to a Telegram account died on `users_email_key`.
    absorbed_releases_email: bool
    # Whether the merged account has collected the signup half of the free
    # period. True if either side did -- their days have just been summed.
    trial_signup_granted: bool
    # Always true after a merge, and that is the rule rather than an accident:
    # the bonus is paid for *connecting* a second identity, and merging is that
    # connection happening. Two accounts that each collected their own signup
    # trial arrive at 7 + 7 by addition; paying the bonus on top would make
    # 21 days reachable by registering twice on purpose.
    trial_link_granted: bool
    # Set when the survivor had no panel account and should adopt the absorbed
    # one instead of leaving it orphaned.
    adopt_panel_uuid: str | None
    adopt_panel_username: str | None
    # Set when the absorbed account's panel profile stays behind and must be
    # expired, or the user would keep a second working connection link holding
    # the very days we just added to the survivor.
    expire_panel_uuid: str | None


def choose_survivor(telegram_account: dict, web_account: dict) -> tuple[dict, dict]:
    """
    Which of two rows keeps existing when they turn out to be one person.

    The Telegram-side row wins. Not because it matters more to the user, but
    because `promo_usage.telegram_id` still references `users(telegram_id)`:
    keeping the row that owns that key avoids rewriting a foreign key under
    live data as part of a merge. Returns `(survivor, absorbed)`.
    """
    return telegram_account, web_account


def plan_merge(*, survivor: dict, absorbed: dict, now: int) -> MergePlan:
    """
    Fold `absorbed` into `survivor`.

    **Days add up.** Both accounts' *remaining* time is summed onto now --
    remaining, not the raw dates, because two expiry timestamps cannot be
    added and an already-lapsed account must contribute zero rather than a
    negative. Someone who bought a month on the website and had two weeks left
    in the bot ends up with six weeks, which is the only answer that does not
    take something they paid for.

    Purchased traffic, gifts given and referrals earned add up for the same
    reason. Email and referrer are taken from the absorbed account only where
    the survivor has none -- a merge should never overwrite a value the
    survivor already had.

    An adopted email also has to be *moved*, not copied, which is what
    `absorbed_releases_email` says: the column is UNIQUE. Where the survivor
    keeps its own address the absorbed row keeps its one too, and both go on
    working as sign-in routes because the lookup follows `merged_into`.
    """
    survivor_left = max(0, int(survivor.get("subscription_ends") or 0) - now)
    absorbed_left = max(0, int(absorbed.get("subscription_ends") or 0) - now)

    survivor_uuid = survivor.get("remnawave_uuid")
    absorbed_uuid = absorbed.get("remnawave_uuid")

    # The survivor adopts the absorbed panel account only when it has none of
    # its own. Otherwise that account is left over, and it has to be expired:
    # its days were just added to the survivor, so leaving it live would hand
    # the user the same period twice on two different links.
    adopt = absorbed_uuid if (not survivor_uuid and absorbed_uuid) else None
    expire = absorbed_uuid if (survivor_uuid and absorbed_uuid) else None

    return MergePlan(
        survivor_id=str(survivor["id"]),
        absorbed_id=str(absorbed["id"]),
        subscription_ends=now + survivor_left + absorbed_left,
        lte_paid_balance_bytes=(
            max(0, int(survivor.get("lte_paid_balance_bytes") or 0))
            + max(0, int(absorbed.get("lte_paid_balance_bytes") or 0))
        ),
        gifted_subscriptions=(
            int(survivor.get("gifted_subscriptions") or 0)
            + int(absorbed.get("gifted_subscriptions") or 0)
        ),
        referred_people=(
            int(survivor.get("referred_people") or 0)
            + int(absorbed.get("referred_people") or 0)
        ),
        email=survivor.get("email") or absorbed.get("email") or None,
        referrer_tag=survivor.get("referrer_tag") or absorbed.get("referrer_tag") or None,
        absorbed_releases_email=bool(absorbed.get("email")) and not survivor.get("email"),
        trial_signup_granted=bool(
            survivor.get("trial_signup_granted") or absorbed.get("trial_signup_granted")
        ),
        trial_link_granted=True,
        adopt_panel_uuid=str(adopt) if adopt else None,
        adopt_panel_username=absorbed.get("remnawave_username") if adopt else None,
        expire_panel_uuid=str(expire) if expire else None,
    )


def days_from(timestamp: int, now: int) -> int:
    """
    Days between now and a timestamp, rounded up, never negative.

    Up rather than down: granting exactly seven days and then reporting them
    reads "6 дн." under truncation, because a few milliseconds have passed by
    the time anyone looks. The customer is told they were short-changed by a
    day on the same screen that just promised seven. A part-day of service is
    a day the subscription still works.
    """
    return max(0, -(-(timestamp - now) // SECONDS_IN_DAY))

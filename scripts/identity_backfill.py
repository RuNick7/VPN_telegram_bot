"""
Deciding what to backfill when moving users off telegram_id as their identity.

Pure functions only -- no panel, no database. `scripts/backfill_identity.py`
supplies the I/O around them. Split this way because the decisions are the
part worth testing, and because a migration script that cannot be exercised
without a live panel is a migration script nobody exercises.

The two questions this answers, per panel account:

  1. Which of our users is this? The panel's own `telegramId` field when it is
     filled; otherwise the username, which for every account created before
     the rework *is* the Telegram ID.
  2. What has to be written? Our row learns the panel UUID; the panel learns
     the Telegram ID it was missing.

Anything ambiguous produces a problem rather than a guess. Picking wrong here
attaches one person's subscription to another person's account.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Telegram IDs are positive and comfortably below 2^52. The bound exists to
# reject a username that happens to be digits but is plainly not an ID -- a
# panel account called "1" or "99999999999999999999" is not somebody's chat.
MIN_TELEGRAM_ID = 10_000
MAX_TELEGRAM_ID = 1 << 52

# Panel usernames we mint ourselves start with this; see identity.py.
OWN_USERNAME_PREFIX = "u-"


def infer_telegram_id(panel_user: dict) -> tuple[int | None, str]:
    """
    Whose account this is, and how we worked that out.

    Returns `(telegram_id, source)` where source is `"panel_field"`,
    `"username"`, or `"unknown"`.

    The panel's own `telegramId` field wins when it is set, because an
    operator or an earlier create call put it there deliberately. Falling back
    to the username is what makes the pre-rework population recoverable at
    all: those accounts were created as `str(telegram_id)` and carry no other
    link to a person.
    """
    raw = panel_user.get("telegramId", panel_user.get("telegram_id"))
    if raw not in (None, "", 0, "0"):
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 0
        if MIN_TELEGRAM_ID <= value <= MAX_TELEGRAM_ID:
            return value, "panel_field"

    username = str(panel_user.get("username") or "").strip()
    if username.isdigit():
        value = int(username)
        if MIN_TELEGRAM_ID <= value <= MAX_TELEGRAM_ID:
            return value, "username"

    return None, "unknown"


def is_own_username(panel_user: dict) -> bool:
    """Whether this account was already named by the new scheme."""
    return str(panel_user.get("username") or "").startswith(OWN_USERNAME_PREFIX)


@dataclass(frozen=True)
class AccountPlan:
    """What one panel account needs, if anything."""

    panel_uuid: str
    panel_username: str
    telegram_id: int | None = None
    telegram_id_source: str = "unknown"
    user_id: str | None = None
    # Write the panel UUID/username onto our row.
    link_db: bool = False
    # Fill the panel's empty `telegramId` field.
    set_panel_telegram_id: bool = False
    # Non-None means: do nothing, a human should look.
    problem: str | None = None

    @property
    def is_noop(self) -> bool:
        return not (self.link_db or self.set_panel_telegram_id) and self.problem is None


@dataclass
class Report:
    plans: list[AccountPlan] = field(default_factory=list)
    # Users in our database that no panel account maps to.
    users_without_panel: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.plans),
            "link_db": sum(1 for p in self.plans if p.link_db),
            "set_panel_telegram_id": sum(1 for p in self.plans if p.set_panel_telegram_id),
            "problems": sum(1 for p in self.plans if p.problem),
            "already_done": sum(1 for p in self.plans if p.is_noop),
            "users_without_panel": len(self.users_without_panel),
        }


def plan_backfill(panel_users: list[dict], db_rows: list[dict]) -> Report:
    """
    Work out every write the backfill would make.

    `db_rows` are our `users` rows; only `id`, `telegram_id` and
    `remnawave_uuid` are read. Nothing here writes anything -- the caller
    decides whether to apply the result.
    """
    by_telegram_id: dict[int, dict] = {}
    for row in db_rows:
        telegram_id = row.get("telegram_id")
        if telegram_id is not None:
            by_telegram_id[int(telegram_id)] = row

    uuid_to_row: dict[str, dict] = {
        str(row["remnawave_uuid"]): row for row in db_rows if row.get("remnawave_uuid")
    }

    # A Telegram ID claimed by two panel accounts cannot be resolved by
    # guessing which one is real -- both get reported instead.
    seen: dict[int, list[str]] = {}
    for panel_user in panel_users:
        telegram_id, _ = infer_telegram_id(panel_user)
        if telegram_id is not None and panel_user.get("uuid"):
            seen.setdefault(telegram_id, []).append(str(panel_user["uuid"]))
    duplicated = {tid for tid, uuids in seen.items() if len(uuids) > 1}

    report = Report()
    matched_user_ids: set[str] = set()

    for panel_user in panel_users:
        plan = _plan_one(panel_user, by_telegram_id, uuid_to_row, duplicated)
        report.plans.append(plan)
        if plan.user_id:
            matched_user_ids.add(plan.user_id)

    report.users_without_panel = [
        str(row["id"]) for row in db_rows if str(row["id"]) not in matched_user_ids
    ]
    return report


def _plan_one(
    panel_user: dict,
    by_telegram_id: dict[int, dict],
    uuid_to_row: dict[str, dict],
    duplicated: set[int],
) -> AccountPlan:
    uuid = str(panel_user.get("uuid") or "")
    username = str(panel_user.get("username") or "")

    if not uuid:
        return AccountPlan(
            panel_uuid="", panel_username=username,
            problem="panel account has no uuid",
        )

    # Already attached to one of our rows: nothing to do, whatever it is
    # called. Checked first so a re-run of the script is free.
    existing = uuid_to_row.get(uuid)
    if existing is not None:
        return AccountPlan(
            panel_uuid=uuid, panel_username=username, user_id=str(existing["id"]),
            telegram_id=existing.get("telegram_id"), telegram_id_source="already_linked",
        )

    telegram_id, source = infer_telegram_id(panel_user)

    if telegram_id is None:
        # A `u-...` account with no owner is one we created and then lost the
        # row for -- rare, but not something to attach to a stranger.
        if is_own_username(panel_user):
            return AccountPlan(
                panel_uuid=uuid, panel_username=username,
                problem="new-style account with no matching user row",
            )
        return AccountPlan(
            panel_uuid=uuid, panel_username=username,
            problem="cannot tell whose account this is (no telegramId, username is not an ID)",
        )

    if telegram_id in duplicated:
        return AccountPlan(
            panel_uuid=uuid, panel_username=username,
            telegram_id=telegram_id, telegram_id_source=source,
            problem=f"telegram_id {telegram_id} is claimed by more than one panel account",
        )

    row = by_telegram_id.get(telegram_id)
    if row is None:
        return AccountPlan(
            panel_uuid=uuid, panel_username=username,
            telegram_id=telegram_id, telegram_id_source=source,
            problem=f"no user row for telegram_id {telegram_id}",
        )

    if row.get("remnawave_uuid"):
        # The row already points at a *different* panel account. Overwriting
        # would silently move the user onto this one.
        return AccountPlan(
            panel_uuid=uuid, panel_username=username,
            telegram_id=telegram_id, telegram_id_source=source, user_id=str(row["id"]),
            problem=(
                f"user already linked to panel account {row['remnawave_uuid']}"
            ),
        )

    return AccountPlan(
        panel_uuid=uuid,
        panel_username=username,
        telegram_id=telegram_id,
        telegram_id_source=source,
        user_id=str(row["id"]),
        link_db=True,
        # Fill the panel's own field when it was empty and we deduced the ID
        # from the username. After this the account carries its owner
        # explicitly, so nothing has to parse a username ever again.
        set_panel_telegram_id=(source == "username"),
    )

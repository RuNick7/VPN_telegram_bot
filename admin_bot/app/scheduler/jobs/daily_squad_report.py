"""
Daily headcount, so capacity is a decision rather than a surprise.

This replaces the "squad is 75% full" alert. That alert existed because users
were split across `internal-1..N` with a hard cap per squad, and crossing it
meant the code had to create another one. Neither is true now: everyone paying
sits in one squad and load is spread by balancers in front of the nodes.

So the number stopped being a fault condition and became information. Nothing
here decides anything or warns about anything -- it reports how many people are
in each squad once a day, and an operator decides whether that means buying
another server.

Sent even when the numbers are dull. A report that only arrives when something
is wrong teaches you to read its absence as "fine", and that is exactly the
habit that hides a job which quietly stopped running.

It also carries the day's enforcement counts -- demotions, traffic blocks and
the rest. Those used to be a message from the monitors the moment they
happened, which with a five-minute interval meant a notification per routine
cut-off, all day. The cost of that is not the noise: it is that the failure
alerts sitting in the same chat stop being read. So the routine outcomes are
recorded to `enforcement_events` as they occur and counted here once, and only
the failures still interrupt anybody.
"""

import logging
import time
from html import escape

from tgvpn_shared.db import EnforcementRepository, LteRepository, UserRepository
from tgvpn_shared.squads import members_count

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)

JOB_NAME = "daily_squad_report"

_users = UserRepository()
_lte = LteRepository()
_enforcement = EnforcementRepository()

# The window the action counts cover. A day, because that is how often this
# runs -- a longer one would double-count yesterday and a shorter one would
# drop the hours between the last run and this one.
_WINDOW_SECONDS = 24 * 60 * 60

# How long an action stays in `enforcement_events` before being pruned. Long
# enough to look back over a bad week, short enough that the table stays
# something you can read.
_RETENTION_DAYS = 30

# What each recorded action is called in the report, in the order they read
# best: the two cut-offs, then the two ways access comes back, then the drift
# case. Keys are the strings the monitors record.
_ACTION_LABELS = (
    ("demoted", "понижено в FREE"),
    ("blocked", "заблокировано по трафику"),
    ("promoted", "возвращено в платный"),
    ("unblocked", "разблокировано по трафику"),
    ("recut", "повторный обрыв соединения"),
)


def format_report(
    *,
    squad_members: dict[str, int],
    paid_squad_name: str,
    tier_counts: dict[str, int],
    active_subscriptions: int,
    actions: dict[str, int] | None = None,
) -> str:
    """
    The message an operator reads over morning coffee.

    Two sources on purpose. Squad membership is what the *panel* believes and
    is what actually determines server load; our own counts are what the
    *database* believes. They should agree, and the day they do not is worth
    seeing side by side rather than discovering during an incident.
    """
    paid_members = squad_members.get(paid_squad_name.lower(), 0)

    # Squad names come from the panel, so they are escaped: an operator who
    # names a squad `<test>` should get a report, not a parse error.
    lines = [
        "📊 <b>Ежедневный отчёт</b>",
        "",
        f"<b>Сквад «{escape(paid_squad_name)}»</b>: {paid_members} чел.",
    ]

    others = sorted(
        (name, count) for name, count in squad_members.items() if name != paid_squad_name.lower()
    )
    if others:
        lines.append("")
        lines.append("<b>Остальные сквады</b>")
        lines.extend(f"• {escape(name)}: {count} чел." for name, count in others)

    lines.extend([
        "",
        "<b>По нашей базе</b>",
        f"• активных подписок: {active_subscriptions}",
        f"• в платном тире: {tier_counts.get('paid', 0)}",
        f"• на бесплатном: {tier_counts.get('free', 0)}",
        f"• ещё не размечено: {tier_counts.get('unknown', 0)}",
    ])

    # Every known action gets a line, zero included. These used to arrive as
    # separate messages the moment they happened, and the reason they are here
    # instead is that they are routine -- so an absent line would read as
    # "nothing happened" when it actually means "this stopped being counted".
    counts = actions or {}
    lines.append("")
    lines.append("<b>Действия за сутки</b>")
    lines.extend(f"• {label}: {counts.get(key, 0)}" for key, label in _ACTION_LABELS)

    # Anything recorded that this report does not know the name of. Better a
    # raw key in the message than a number that silently never appears.
    for key in sorted(set(counts) - {key for key, _ in _ACTION_LABELS}):
        lines.append(f"• {escape(key)}: {counts[key]}")

    return "\n".join(lines)


async def run_daily_squad_report() -> None:
    """Scheduled entry point. Never raises -- the scheduler must keep ticking."""
    client = RemnawaveClient()
    try:
        squads = await client.list_internal_squads()
        squad_members = {
            str(squad.get("name") or "?").strip().lower(): members_count(squad)
            for squad in squads
        }

        stats = await _users.get_stats()
        tier_counts = await _lte.get_tier_counts()
        actions = await _enforcement.summary_since(_WINDOW_SECONDS)

        await send_admin_message(
            format_report(
                squad_members=squad_members,
                paid_squad_name=settings.paid_squad_name,
                tier_counts=tier_counts,
                active_subscriptions=int(stats.get("active", 0)),
                actions=actions,
            ),
            html_body=True,
        )
        logger.info("Daily squad report sent at %s", int(time.time()))
    except Exception as exc:
        logger.error("Daily squad report failed: %s", exc, exc_info=True)
        try:
            await send_admin_message(f"❌ Не удалось собрать ежедневный отчёт.\nПричина: {exc}")
        except Exception as send_err:
            logger.error("Could not report the failure either: %s", send_err)
    finally:
        await client.close()

    # After the report, and on its own: the log is bounded by this and by
    # nothing else, but a prune that fails must not cost anybody the numbers
    # it was about to trim.
    try:
        pruned = await _enforcement.prune(_RETENTION_DAYS)
        if pruned:
            logger.info("Pruned %d enforcement events older than %d days", pruned, _RETENTION_DAYS)
    except Exception as exc:
        logger.warning("Could not prune the enforcement log: %s", exc)

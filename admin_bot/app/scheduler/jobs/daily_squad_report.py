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
"""

import logging
import time
from html import escape

from tgvpn_shared.db import LteRepository, UserRepository
from tgvpn_shared.squads import members_count

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.notify.admin import send_admin_message

logger = logging.getLogger(__name__)

JOB_NAME = "daily_squad_report"

_users = UserRepository()
_lte = LteRepository()


def format_report(
    *,
    squad_members: dict[str, int],
    paid_squad_name: str,
    tier_counts: dict[str, int],
    active_subscriptions: int,
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

        await send_admin_message(
            format_report(
                squad_members=squad_members,
                paid_squad_name=settings.paid_squad_name,
                tier_counts=tier_counts,
                active_subscriptions=int(stats.get("active", 0)),
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

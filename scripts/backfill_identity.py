#!/usr/bin/env python
"""
Move existing users onto our own identity, one-off.

Before the rework a user *was* their Telegram ID: the panel account was named
`str(telegram_id)` and nothing recorded which panel row belonged to whom. This
walks the panel, works out whose each account is, and writes that link down --
`users.remnawave_uuid` on our side, and the panel's own `telegramId` field
where it was left empty.

Running it is not required. The bot backfills the same link lazily, the first
time it looks a legacy user up. This exists to do the whole population at once
so the legacy path stops being exercised, and so the report tells you about
accounts that *cannot* be matched -- which lazy backfill would never surface.

    # look, change nothing (default)
    python scripts/backfill_identity.py

    # write to our database only, leave the panel untouched
    python scripts/backfill_identity.py --apply

    # also fill the panel's empty telegramId fields
    python scripts/backfill_identity.py --apply --write-panel

Safe to re-run: an account already linked is a no-op, and nothing that looks
ambiguous is ever written.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from identity_backfill import Report, plan_backfill  # noqa: E402

from tgvpn_shared.db import UserRepository, close_pool, get_pool  # noqa: E402
from tgvpn_shared.remnawave import RemnawaveClient  # noqa: E402
from tgvpn_shared.settings import get_settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

_users = UserRepository()


def build_client() -> RemnawaveClient:
    settings = get_settings()
    settings.require("remnawave_base_url")
    return RemnawaveClient(
        base_url=settings.remnawave_base_url,
        token=settings.remnawave_api_token,
        username=settings.remnawave_username or None,
        password=settings.remnawave_password or None,
        timeout_seconds=settings.remnawave_timeout_seconds,
    )


async def load_db_rows() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, telegram_id, remnawave_uuid, telegram_tag FROM users WHERE merged_into IS NULL"
    )
    return [dict(row) for row in rows]


async def load_panel_users(client: RemnawaveClient) -> list[dict]:
    return [user async for user in client.iter_all_users()]


def print_report(report: Report, *, verbose: bool) -> None:
    counts = report.counts()
    logger.info("")
    logger.info("Panel accounts seen:        %s", counts["total"])
    logger.info("  already linked:           %s", counts["already_done"])
    logger.info("  to link in our database:  %s", counts["link_db"])
    logger.info("  to fill telegramId in panel: %s", counts["set_panel_telegram_id"])
    logger.info("  need a human:             %s", counts["problems"])
    logger.info("Users with no panel account: %s", counts["users_without_panel"])

    problems = [plan for plan in report.plans if plan.problem]
    if problems:
        logger.info("")
        logger.info("Nothing was written for these:")
        for plan in problems:
            logger.info("  %-40s %s", plan.panel_username or plan.panel_uuid, plan.problem)

    if verbose:
        logger.info("")
        for plan in report.plans:
            if plan.link_db or plan.set_panel_telegram_id:
                logger.info(
                    "  %-20s tg=%-12s via %-12s -> user %s%s",
                    plan.panel_username, plan.telegram_id, plan.telegram_id_source,
                    plan.user_id,
                    "  (+panel telegramId)" if plan.set_panel_telegram_id else "",
                )


async def apply_plans(report: Report, client: RemnawaveClient, *, write_panel: bool) -> None:
    linked = panel_written = failed = 0

    for plan in report.plans:
        if plan.problem or not plan.user_id:
            continue

        if plan.link_db:
            try:
                await _users.set_panel_identity(
                    plan.user_id,
                    remnawave_uuid=plan.panel_uuid,
                    remnawave_username=plan.panel_username,
                )
                linked += 1
            except Exception as exc:
                failed += 1
                logger.error("  link %s failed: %s", plan.panel_username, exc)
                # Skip the panel write too: a half-applied account is worse
                # than one left entirely alone for the next run.
                continue

        if write_panel and plan.set_panel_telegram_id and plan.telegram_id:
            try:
                await client.update_user(
                    {"uuid": plan.panel_uuid, "telegramId": int(plan.telegram_id)}
                )
                panel_written += 1
            except Exception as exc:
                failed += 1
                logger.error("  panel telegramId for %s failed: %s", plan.panel_username, exc)

    logger.info("")
    logger.info("Written: %s links, %s panel telegramId fields, %s failures",
                linked, panel_written, failed)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="write the links to our database (default: report only, change nothing)",
    )
    parser.add_argument(
        "--write-panel", action="store_true",
        help="also fill the panel's empty telegramId fields (requires --apply)",
    )
    parser.add_argument("--verbose", action="store_true", help="list every planned write")
    args = parser.parse_args()

    if args.write_panel and not args.apply:
        parser.error("--write-panel does nothing without --apply")

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL is not set.")
        return 2

    client = build_client()
    try:
        logger.info("Reading the panel...")
        panel_users = await load_panel_users(client)
        logger.info("Reading our database...")
        db_rows = await load_db_rows()

        report = plan_backfill(panel_users, db_rows)
        print_report(report, verbose=args.verbose)

        if not args.apply:
            logger.info("")
            logger.info("Dry run -- nothing was written. Re-run with --apply to write.")
            return 0

        if not args.write_panel:
            logger.info("")
            logger.info("Writing links only; the panel is not being modified "
                        "(add --write-panel to fill telegramId).")
        await apply_plans(report, client, write_panel=args.write_panel)
        return 0
    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

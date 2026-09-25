#!/usr/bin/env python
"""
Create panel accounts for every user in our database that has none, one-off.

For bringing a fresh panel up against an existing database: after a panel
rebuild, or on a first deployment. Our database is the authority here -- the
panel is being reconstructed from it, so each account is created with the
expiry we already hold, and a user who has never had a subscription gets the
trial instead.

    # look, change nothing (default)
    python scripts/provision_panel_users.py

    # actually create the accounts
    python scripts/provision_panel_users.py --apply

    # override the trial for users who have never had a subscription
    python scripts/provision_panel_users.py --apply --trial-days 0

Safe to re-run: a user who already has a panel account is skipped, matched on
the stored UUID *and* on either name we would look them up by -- so a user
whose link was simply never recorded does not get a second account.

Run `scripts/backfill_identity.py` first if the panel already has accounts
whose links were never written down. Otherwise this cannot tell "no account"
from "account we lost track of", and errs toward creating a duplicate only
when the name does not match either.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from panel_provision import Plan, plan_provisioning  # noqa: E402

from tgvpn_shared.db import UserRepository, close_pool, get_pool  # noqa: E402
from tgvpn_shared.free_tier import format_panel_timestamp, panel_expire_timestamp  # noqa: E402
from tgvpn_shared.remnawave import RemnawaveClient  # noqa: E402
from tgvpn_shared.settings import get_settings  # noqa: E402
from tgvpn_shared.squads import resolve_paid_squad_uuid  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("provision")

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
        """
        SELECT id, telegram_id, remnawave_uuid, remnawave_username, merged_into,
               EXTRACT(EPOCH FROM subscription_ends)::bigint AS subscription_ends
        FROM users
        """
    )
    return [dict(row) for row in rows]


async def load_panel_index(client: RemnawaveClient) -> tuple[set[str], set[str]]:
    """Every UUID and username the panel currently holds."""
    uuids: set[str] = set()
    usernames: set[str] = set()
    async for user in client.iter_all_users():
        if user.get("uuid"):
            uuids.add(str(user["uuid"]))
        if user.get("username"):
            usernames.add(str(user["username"]))
    return uuids, usernames


def print_plan(plan: Plan, *, verbose: bool) -> None:
    counts = plan.counts()
    logger.info("")
    logger.info("Users in our database:     %s", counts["users"])
    logger.info("  already in the panel:    %s", counts["already_have"])
    logger.info("  to create:               %s", counts["create"])
    logger.info("    of those, with trial:  %s", counts["with_trial"])
    logger.info("  skipped:                 %s", counts["skipped"])

    if plan.skipped:
        logger.info("")
        logger.info("Skipped:")
        for user_id, reason in plan.skipped[:20]:
            logger.info("  %-38s %s", user_id, reason)
        if len(plan.skipped) > 20:
            logger.info("  ... and %s more", len(plan.skipped) - 20)

    if verbose:
        logger.info("")
        for item in plan.to_create:
            logger.info(
                "  %-22s tg=%-12s %s%s",
                item.username, item.telegram_id, item.reason,
                f" (+{item.trial_days}d trial)" if item.is_trial else "",
            )


async def assign_squad(client: RemnawaveClient, user_uuid: str) -> None:
    """Place a freshly created account into the paid squad."""
    squad_uuid = await resolve_paid_squad_uuid(client, get_settings().paid_squad_name)
    if squad_uuid:
        await client.set_user_squads([user_uuid], [str(squad_uuid)])


async def apply_plan(plan: Plan, client: RemnawaveClient) -> None:
    created = failed = 0

    for item in plan.to_create:
        payload = {
            "username": item.username,
            "expireAt": format_panel_timestamp(panel_expire_timestamp(item.expire_ts)),
            "activateAllInbounds": True,
        }
        if item.telegram_id is not None:
            payload["telegramId"] = int(item.telegram_id)

        try:
            panel_user = await client.create_user(payload)
            user_uuid = panel_user.get("uuid")
            if not user_uuid:
                raise RuntimeError("panel returned no uuid")

            # Recorded before the squad call: the account exists either way,
            # and a link we failed to write is the one thing that would make a
            # re-run create a duplicate.
            await _users.set_panel_identity(
                item.user_id,
                remnawave_uuid=str(user_uuid),
                remnawave_username=item.username,
            )
            if item.is_trial:
                # Written by internal id, not telegram_id: a website account
                # has none, and moving `subscription_ends` off zero is what
                # stops a later run granting the same person a second trial.
                await _users.set_subscription_ends(item.user_id, item.expire_ts)

            await assign_squad(client, str(user_uuid))
            created += 1
        except Exception as exc:
            failed += 1
            logger.error("  %s failed: %s", item.username, exc)

    logger.info("")
    logger.info("Created: %s accounts, %s failures", created, failed)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="create the accounts (default: report only, change nothing)",
    )
    parser.add_argument(
        "--trial-days", type=int, default=None,
        help="days to grant users who have never had a subscription "
             "(default: TRIAL_DAYS from the environment)",
    )
    parser.add_argument("--verbose", action="store_true", help="list every account to be created")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL is not set.")
        return 2

    settings = get_settings()
    trial_days = args.trial_days if args.trial_days is not None else settings.trial_days
    if trial_days < 0:
        parser.error("--trial-days cannot be negative")

    client = build_client()
    try:
        logger.info("Reading the panel...")
        panel_uuids, panel_usernames = await load_panel_index(client)
        logger.info("Reading our database...")
        db_rows = await load_db_rows()

        plan = plan_provisioning(
            db_rows, panel_uuids, panel_usernames,
            now=int(time.time()), trial_days=trial_days,
        )
        logger.info("Trial for users who have never had a subscription: %s days", trial_days)
        print_plan(plan, verbose=args.verbose)

        if not args.apply:
            logger.info("")
            logger.info("Dry run -- nothing was created. Re-run with --apply to create.")
            return 0

        await apply_plan(plan, client)
        return 0
    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

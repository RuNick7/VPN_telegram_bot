# Phase 3 rollout: FREE tier and LTE quotas

Both features ship **off**. Deploying the code changes nothing until the flags
below are set, which is deliberate — read the warning first.

## Why enabling the FREE tier is a real decision

Normally Remnawave expires an account itself: `expireAt` passes and access
stops, whatever else is broken.

With `FREE_TIER_ENABLED=true` that stops being true. Panel accounts are held
open ~10 years so a lapsed user can still reach the limited FREE servers, and
`subscription_expire_monitor` becomes the *only* thing moving expired users off
paid squads. If that job stops running, **every expired subscriber keeps full
paid access indefinitely**, and nothing looks wrong from the outside.

Three things exist to make that state visible, and they are the reason this is
safe to run — not the reason it can be turned on without thought:

- every run writes to `job_runs`, and `service_health_monitor` alerts when the
  job has not *succeeded* within 2× its interval (default 10 min);
- a catch-up sweep runs at startup, so downtime is reconciled immediately;
- a missing FREE squad aborts the run loudly instead of skipping demotion.

## 1. Create the squads in Remnawave

Three squads, all managed by hand in the panel — nothing in this codebase
creates one. Named exactly:

| Squad | Setting | Required |
|---|---|---|
| paid | `PAID_SQUAD_NAME` (default `internal`) | yes |
| free | `FREE_SQUAD_NAME` (default `FREE`) | yes |
| LTE | `LTE_SQUAD_NAME` (default `LTE`) | only with quotas |

Give FREE only the inbounds you're willing to hand out for nothing.

Everyone who is paying goes into the one paid squad. Users are **not** spread
across `internal-1..N` any more — that existed to cap members per squad, and
load is now handled by balancers in front of the nodes instead. If you are
migrating from the old layout, move everyone into the single squad in the
panel first; the bots read whatever `PAID_SQUAD_NAME` points at and will not
find users left behind in `internal-2`.

A missing FREE **or** paid squad aborts the reconciliation run loudly. The
paid one matters just as much: without it nobody is promoted after paying, so
customers are charged and get nothing, with silence as the only symptom.

Check what exists:

```bash
docker compose exec bots python3 -c "
import sys; sys.path.insert(0, '/app/admin_bot')
import asyncio
from app.api.client import RemnawaveClient
async def main():
    c = RemnawaveClient()
    try:
        for s in await c.list_internal_squads():
            print(s.get('name'), (s.get('info') or {}).get('membersCount'))
    finally:
        await c.close()
asyncio.run(main())
"
```

Enabling with the squad missing is safe — the job refuses to run and messages
the admins — but it means expiry is not being enforced, so fix it promptly.

## 2. Confirm the alert actually fires, before trusting it

Do this *before* step 3, not after. The whole design rests on the alert
working, and an alert nobody has ever seen fire is an assumption.

Backdate the recorded success and confirm an alert is produced:

```sql
UPDATE job_runs SET last_success_at = now() - INTERVAL '25 minutes'
WHERE job_name = 'subscription_expire_monitor';
```

Within one monitor interval the admins should receive
`🚨 Мониторинг сервисов` naming the stale job. If nothing arrives, stop —
`ADMIN_IDS`, the scheduler, or the health monitor is misconfigured, and the
FREE tier must not be enabled until it is fixed.

## 3. Enable, watching the first sweep

```bash
FREE_TIER_ENABLED=true
FREE_SQUAD_NAME=FREE
```

Restart and watch: the catch-up sweep runs at startup and reports how many
users it moved. On a first enable that number is roughly "everyone currently
expired", which is expected — but sanity-check it against the statistics
screen before walking away.

New and renewed accounts get the far-future `expireAt` from this point on.
**Accounts created before enabling keep their real expiry** and will still be
cut off by the panel when it passes; they pick up the new behaviour on their
next renewal. Nobody loses access early because of the switch.

## 4. LTE quotas (optional, independent)

```bash
LTE_ENABLED=true
LTE_SQUAD_NAME=LTE
LTE_CYCLE_DAYS=30
LTE_FREE_GB_PER_CYCLE=10
LTE_NODE_NAME_KEYWORDS=lte      # or LTE_NODE_UUIDS=<uuid>,<uuid>
```

Only traffic on the matched nodes counts. If nothing matches, the monitor logs
a warning and enforces nothing — it never falls back to metering every node,
because a configuration slip would otherwise block everyone at once.

Purchased traffic carries across cycles; the free allowance does not.

**Naming**: customers never see "LTE". Everywhere a user can read it — the
devices menu, the renewal buttons, the purchase screens, the low-traffic
warnings — this is **«Трафик белых списков»**, defined once as
`TRAFFIC_LABEL` in `shared/tgvpn_shared/lte_quota.py`. Env vars, columns,
callback data and job names stay `lte_*`: renaming them would mean a
migration plus an `.env` edit on every deployment and change nothing a user
sees. So `LTE_ENABLED=true` above is what switches «белые списки» on.

## Turning it back off

Set `FREE_TIER_ENABLED=false` and restart. The job stops, and panel `expireAt`
returns to the real subscription date on each user's next renewal — but users
already holding a far-future `expireAt` **stay unexpiring until they renew**,
so run one final reconciliation, or correct them manually, before assuming
expiry is enforced by the panel again.

## Rollback

`migrations/0002_free_lte_squads.down.sql` drops the LTE columns and
`job_runs`. Only needed if reverting the schema itself; disabling the flags is
enough to stop the behaviour.

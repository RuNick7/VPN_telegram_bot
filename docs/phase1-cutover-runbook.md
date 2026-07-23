# Phase 1 cutover runbook: SQLite → PostgreSQL

Run this on the real server, once you're ready to switch production over.
Everything up to this point (schema, Docker Compose, repository layer, ETL
script) has only been built and tested locally/in CI, against synthetic
data -- this is the first time it touches real data. Read the whole thing
before starting; the cutover itself should take a few minutes of downtime.

## Before you start

- [ ] Take a full filesystem/VM snapshot or copy of the server, if that's
      available to you. This is the cheapest possible rollback path.
- [ ] Confirm `docker` and `docker compose` are installed on the server.
- [ ] Confirm the real `.env` has real values for everything in
      `.env.example` (bot tokens, YooKassa keys, Remnawave credentials) --
      copy your current production `.env` and add the new Postgres
      variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
      `DATABASE_URL`) alongside it.
- [ ] Locate the live `subscription.db` path (whatever `DB_PATH`/
      `USER_BOT_DB_PATH` currently point to in production).
- [ ] Pick a maintenance window. Users mid-payment during the window will
      have their webhook retried by YooKassa afterward (the atomic claim
      logic handles this safely either way), but they won't get an
      immediate response while everything is down.

## 1. Stop the writers

Stop all three processes that currently write to `subscription.db`:
admin_bot, user_bot (polling), user_bot webhook. However you run them
today (systemd, screen, manually) -- stop them now. This freezes the
source file so the snapshot in the next step is consistent.

## 2. Snapshot the live SQLite file

```bash
cp /path/to/subscription.db /path/to/subscription.db.pre-postgres-backup
```

Keep this backup somewhere safe until you're confident the cutover
succeeded -- it's the rollback path (see the bottom of this doc).

## 3. Stand up Postgres

From the repo root on the server:

```bash
docker compose up -d postgres
```

Wait for it to report healthy:

```bash
docker compose ps postgres
```

## 4. Apply the schema

```bash
docker compose up migrate
```

Confirm it printed `<n>/u init (...)` and exited 0, not an error. If you
ever need to inspect the schema manually:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt'
```

## 5. Run the ETL

```bash
python3 -m venv /tmp/etl-venv
/tmp/etl-venv/bin/pip install asyncpg
/tmp/etl-venv/bin/python scripts/etl_sqlite_to_postgres.py \
    --sqlite-path /path/to/subscription.db.pre-postgres-backup \
    --database-url "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@127.0.0.1:${POSTGRES_HOST_PORT:-5433}/$POSTGRES_DB"
```

Read its output carefully:

- The `subscription: N source rows -> M unique telegram_id rows` line --
  if `N` and `M` differ by more than a handful, the legacy duplicate-row
  issue was worse than expected; spot-check a few of the affected
  telegram_ids afterward (see step 6).
- Any `skipped N promo_usage rows with no matching users.telegram_id` --
  expected to be small/zero; these are usage records for telegram_ids that
  had no subscription row at all.
- The final verification table -- row counts should match the source
  counts printed earlier (minus the promo_usage skips just mentioned).

The script is safe to re-run if something looks wrong and you want to
retry after investigating (see its docstring for exactly what's idempotent
and what isn't).

## 6. Spot-check real data

Before trusting the migration, manually verify a handful of accounts you
know the state of -- pick 3-5 telegram_ids you recognize (yours, a
teammate's, a known active subscriber) and compare:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT telegram_id, telegram_tag, subscription_ends, referred_people, gifted_subscriptions FROM users WHERE telegram_id IN (111111111, 222222222);"
```

against what you remember from the bot (`/ref`, `/gift`, admin search) on
the old system before you stopped it.

## 7. Flip over and restart

Update the real `.env` so `DATABASE_URL` points at the Postgres you just
populated (if it isn't already, from step 0). Then:

```bash
docker compose up -d --build admin_bot user_bot user_bot_webhook
```

## 8. Smoke test

- `curl http://localhost:8000/health` -> `{"status": "ok"}`.
- In Telegram: `/start` on a test account, `/ref`, `/pay` through to a real
  tariff screen (don't have to complete a real payment), admin bot's user
  search on one of the accounts you spot-checked in step 6.
- Watch `docker compose logs -f admin_bot user_bot user_bot_webhook` for a
  few minutes for anything unexpected.

## Rollback

If anything looks wrong and you need to revert:

1. `docker compose stop admin_bot user_bot user_bot_webhook`
2. Point `.env`/`DB_PATH` back at
   `/path/to/subscription.db.pre-postgres-backup` (rename it back to the
   original filename first) and redeploy the pre-Phase-1 release.
3. Restart the bots the way you did before this runbook.

The Postgres data isn't touched by a rollback -- it's fine to leave the
`postgres`/`migrate` containers running (or stop them) while you
investigate what went wrong, and re-attempt the cutover later.

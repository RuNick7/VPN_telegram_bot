# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two independent Telegram bots for a VPN-subscription service (Remnawave panel + YooKassa payments), plus a shared Postgres data layer and a legacy web MVP that is being phased out:

- `admin_bot/` — operator-facing aiogram bot: manage Remnawave users/hosts/nodes/squads, promo codes, broadcasts, node/squad monitoring, backups. Entrypoint `admin_bot/main.py`.
- `user_bot/` — customer-facing aiogram bot: signup, subscription purchase via YooKassa, referrals, promo codes, device setup instructions. Two runtime entrypoints against the same codebase: `user_bot/bot.py` (long-polling) and `user_bot/run_webhook.py` (aiohttp server receiving YooKassa payment webhooks at `/webhook-yookassa`).
- `shared/` — installable package (`tgvpn-shared`, imported as `tgvpn_shared`) holding the Postgres repository layer both bots use. See Architecture below.
- `web/` — legacy FastAPI + static-JS MVP for a customer web cabinet. Not wired to the current database layer (its adapters shell out to Python subprocesses importing old `user_bot` modules) and is expected to be replaced rather than extended.

The project was migrated off SQLite onto Postgres; some code (e.g. `shared/tgvpn_shared/sync_bridge.py`, comments in `vpn_service.py`) references this as an ongoing incremental migration rather than a single cutover — don't be surprised by "Phase 1/2" references in comments.

## Commands

### Setup
```bash
pip install -r requirements-dev.txt   # runtime deps + editable shared/ + pytest
cp .env.example .env                  # then fill in real values
```

### Running a bot locally (no Docker)
Requires `.env` at repo root and a reachable Postgres (`DATABASE_URL`):
```bash
python admin_bot/main.py
python user_bot/bot.py            # polling
python user_bot/run_webhook.py    # YooKassa webhook receiver
```

### Full stack via Docker Compose
```bash
docker compose up -d postgres           # isolated Postgres, host port 5433 by default
docker compose up migrate               # applies migrations/*.up.sql (one-off job)
docker compose up -d admin_bot user_bot user_bot_webhook
```
Each bot's `Dockerfile` is built with the **repo root** as build context (`docker-compose.yml` sets `context: .`), because both images need to `COPY shared/` alongside their own bot directory.

### Database migrations
Plain SQL files in `migrations/`, golang-migrate format (`NNNN_name.up.sql` / `.down.sql`). Applied via the `migrate/migrate` Docker image — either `docker compose up migrate`, or directly:
```bash
docker run --rm --network tg_vpn_default -v "$(pwd)/migrations:/migrations" migrate/migrate \
  -path=/migrations -database "postgresql://tgvpn:tgvpn@localhost:5433/tgvpn?sslmode=disable" up
```
(On Windows Git Bash, prefix with `MSYS_NO_PATHCONV=1` or the `-v` path gets mangled.)

### Tests
```bash
docker compose up -d postgres                       # tests need a real Postgres
python -m pytest user_bot/tests/ shared/tests/ -v    # run together
python -m pytest shared/tests/test_payments.py::test_claim_payment_processing_blocks_concurrent_double_claim -v  # single test
```
Tests connect to Postgres at `127.0.0.1:5433` (the compose service's published port, not the internal `postgres` hostname bots use inside the compose network).

**Do not add `admin_bot` to the same pytest run as `user_bot`/`shared`.** Both bots use `app.*` as their internal top-level package name; each has a `conftest.py` that inserts its own directory onto `sys.path`, and collecting both in one process makes `import app...` resolve ambiguously. `admin_bot/conftest.py` exists only for standalone manual verification, e.g.:
```bash
cd admin_bot && python -c "import conftest; import main; print('ok')"
```
`shared/tests/conftest.py` truncates all tables before every test (autouse fixture) — tests assume an otherwise-empty local/CI database, not one with real data.

## Architecture

### Database layer (`shared/`)

`shared/tgvpn_shared/db/` is the **only** sanctioned way either bot touches Postgres. Both bots used to have their own separate SQLite access code (`user_bot/data/db_utils.py`, `admin_bot/app/services/subscription_db.py`, `admin_bot/app/db/sqlite.py`) — all deleted, fully replaced by this package. New DB access should go through here, not ad hoc queries in handler code.

- `pool.py` — one lazily-created asyncpg pool per process, from `DATABASE_URL`.
- `UserRepository` — the `users` table: signup, subscription extension, referrals (`award_referral` is atomic: a referrer is only credited once), admin-side upsert helpers, plus the reminder/nurture-campaign queries.
- `PaymentRepository` — YooKassa payment status. `claim_payment_processing` is an atomic `INSERT ... ON CONFLICT ... WHERE ...` claim that prevents a retried/duplicate webhook delivery from crediting a payment twice.
- `PromoRepository` — promo codes. `try_claim_promo_usage`/`release_promo_usage` atomically claim a code before crediting, and roll back the claim if crediting fails, so a one-time code can't be redeemed by two users racing each other.
- `EventRepository` — click telemetry (`bot_events`).
- `AdminOperatorRepository` — admin-panel roles (table `admin_operators`; historically called `users` in admin_bot's own SQLite file — renamed to stop colliding with the customer-identity `users` table below).

Repository methods take/return **Unix epoch seconds (`int`)** for timestamp fields even though the underlying columns are `TIMESTAMPTZ` — this matches the arithmetic used throughout both bots' handlers (`now_ts + N * 86400`, `sub_ends > now_ts`, ...). Conversion happens in the SQL itself (`to_timestamp($1)` / `EXTRACT(EPOCH FROM ...)::bigint`), not in Python.

The `users` table's `id` (UUID primary key) and columns like `remnawave_uuid`/`merged_into` are schema-ready for a planned identity rework (letting a person exist without a `telegram_id`) that **hasn't landed in application code yet** — every current call site still looks users up by `telegram_id`. Don't assume `id`/`remnawave_uuid`/`merged_into` are populated or read anywhere yet.

`user_bot/app/services/remnawave/vpn_service.py` is a deliberate exception to "always use the repositories": its public functions are synchronous (they make blocking Remnawave HTTP calls via `requests` and are always invoked through `asyncio.to_thread` by callers), so its few DB touches go through `tgvpn_shared/sync_bridge.py`'s `run_sync()` instead — a standalone connection per call via `asyncio.run()`, since the shared asyncpg pool is bound to whichever event loop created it and can't be reused from a throwaway one.

### Remnawave integration

Both bots talk to a Remnawave VPN panel over HTTP, currently through two independent, not-yet-unified clients: `admin_bot/app/api/client.py` (async, official `remnawave_api` SDK + httpx) and `user_bot/app/clients/remnawave/client.py` (sync, raw `requests`). Both accept `REMNAWAVE_TOKEN`/`REMNAWAVE_API_KEY` as interchangeable env var aliases. `remnawave_api` (imported by both bots) and `remnawave` (a separate, similarly-named package) are different packages — don't confuse them when reading Remnawave SDK code or docs.

### Payments

YooKassa. `user_bot/payments/yookassa_client.py` creates payments; `user_bot/payments/webhook.py` receives the success callback. **The webhook has no signature of its own from YooKassa** — the only trustworthy signal is a server-to-server re-fetch of the payment by ID (`fetch_payment`). The handler must never credit a subscription/gift code based on the raw request body (`event`/`status`/`metadata`) alone, only on a verified fetch's own result — this was a real, previously-shipped vulnerability (forgeable free subscriptions), not a hypothetical one, so don't reintroduce a code path that trusts the request body.

### Configuration

Single root-level `.env` (see `.env.example`), loaded via `python-dotenv`/`pydantic-settings`. `admin_bot/app/config/settings.py` uses a pydantic `Settings` model (instantiated at import time — importing it requires `Admin_bot_token` etc. to already be set in the environment). `user_bot` reads `os.getenv` directly in more places; settings are not yet unified between the two bots.

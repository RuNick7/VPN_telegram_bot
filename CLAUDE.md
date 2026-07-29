# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two independent Telegram bots for a VPN-subscription service (Remnawave panel + YooKassa payments), plus a shared package holding everything both bots need, and a legacy web MVP that is being phased out:

- `admin_bot/` — operator-facing aiogram bot: manage Remnawave users/hosts/nodes/squads, promo codes, broadcasts, node/squad monitoring, backups. Entrypoint `admin_bot/main.py`.
- `user_bot/` — customer-facing aiogram bot: signup, subscription purchase via YooKassa, referrals, promo codes, device setup instructions. Two runtime entrypoints against the same codebase: `user_bot/bot.py` (long-polling) and `user_bot/run_webhook.py` (aiohttp server receiving YooKassa payment webhooks at `/webhook-yookassa`).
- `shared/` — installable package (`tgvpn-shared`, imported as `tgvpn_shared`) holding the Postgres repository layer, the Remnawave client, the settings model, and squad-placement logic. See Architecture below.
- `web/` — legacy FastAPI + static-JS MVP for a customer web cabinet. **Currently broken and unused**: its adapters shell out to Python subprocesses importing `user_bot` modules that no longer exist. It is slated for a full rewrite (in Go), so don't repair it — and don't treat its code as a reference for how anything currently works.

The overhaul is running in strictly sequential phases, each tested and deployed before the next begins. Phase 0 (webhook security fix), Phase 1 (SQLite → Postgres, Docker), and Phase 2 (this refactor) are done. Comments referencing "Phase N" mean this sequence.

## Commands

### Setup
```bash
pip install -r requirements-dev.txt   # runtime deps + editable shared/ + pytest
cp .env.example .env                  # then fill in real values
```

### Running locally (no Docker)
Requires `.env` at repo root and a reachable Postgres (`DATABASE_URL`):
```bash
python run_all.py                 # all three processes, supervised
```
Or one at a time, which is what `run_all.py` shells out to:
```bash
python admin_bot/main.py
python user_bot/bot.py            # polling
python user_bot/run_webhook.py    # YooKassa webhook receiver
```
Each entrypoint calls `settings.require(...)` first, so a missing variable fails immediately with a readable message instead of a traceback from deep inside aiogram.

`run_all.py` uses **child processes, not threads** — both bots name their internal package `app`, so one interpreter can't host both (see the pytest note below). If any child exits, the launcher stops the rest rather than leaving a half-running deployment.

### Full stack via Docker Compose
```bash
docker compose up -d              # postgres + migrate + `bots` (all three in one container)
```
To run the three bots as separate services instead — for restarting or tailing one without touching the others:
```bash
docker compose --profile separate up -d admin_bot user_bot user_bot_webhook
```
**Never run both at once**: two pollers on one Telegram token fight over updates, and both bind the webhook port.

Every image is built with the **repo root** as build context (`docker-compose.yml` sets `context: .`), because each needs to `COPY shared/` alongside the bot directories.

### Database migrations
Plain SQL files in `migrations/`, golang-migrate format (`NNNN_name.up.sql` / `.down.sql`). Applied via the `migrate/migrate` Docker image — either `docker compose up migrate`, or directly:
```bash
docker run --rm --network tg_vpn_default -v "$(pwd)/migrations:/migrations" migrate/migrate \
  -path=/migrations -database "postgresql://tgvpn:tgvpn@localhost:5433/tgvpn?sslmode=disable" up
```
(On Windows Git Bash, prefix with `MSYS_NO_PATHCONV=1` or the `-v` path gets mangled.)

### Tests

Most tests need no database. Only `shared/tests/db/` does:
```bash
python -m pytest tests/ user_bot/tests/ shared/tests/ --ignore=shared/tests/db -v   # no Postgres needed
docker compose up -d postgres                                                       # required below
python -m pytest shared/tests/db/ -v
```
The DB tests connect to `127.0.0.1:5433` (the compose service's published port, not the internal `postgres` hostname bots use inside the compose network), and `shared/tests/db/conftest.py` truncates every table before each test — they assume a local/CI database with no real data.

**Do not add `admin_bot` to the same pytest run as `user_bot`/`shared`.** Both bots use `app.*` as their internal top-level package name; each has a `conftest.py` that inserts its own directory onto `sys.path`, and collecting both in one process makes `import app...` resolve ambiguously. Run admin_bot's own suite separately:
```bash
cd admin_bot && python -m pytest tests/ -v
```
The root `tests/` directory holds tests for code that belongs to neither bot (currently `run_all.py`), and must stay free of `admin_bot`/`user_bot` imports for the same reason.

## Architecture

### `shared/` — the code both bots use

Anything used by both bots belongs here, not duplicated on each side. Four modules:

**`db/`** — the **only** sanctioned way either bot touches Postgres. New DB access goes through a repository, not ad hoc queries in handler code.

- `pool.py` — one lazily-created asyncpg pool per process, from `DATABASE_URL`.
- `UserRepository` — the `users` table: signup, subscription extension, referrals (`award_referral` is atomic: a referrer is only credited once), admin-side upsert helpers, plus the reminder/nurture-campaign queries.
- `PaymentRepository` — YooKassa payment status. `claim_payment_processing` is an atomic `INSERT ... ON CONFLICT ... WHERE ...` claim that prevents a retried/duplicate webhook delivery from crediting a payment twice.
- `PromoRepository` — promo codes. `try_claim_promo_usage`/`release_promo_usage` atomically claim a code before crediting, and roll back the claim if crediting fails, so a one-time code can't be redeemed by two users racing each other.
- `EventRepository` — click telemetry (`bot_events`).
- `AdminOperatorRepository` — admin-panel roles (table `admin_operators`; historically called `users` in admin_bot's own SQLite file — renamed to stop colliding with the customer-identity `users` table).

Repository methods take/return **Unix epoch seconds (`int`)** for timestamp fields even though the underlying columns are `TIMESTAMPTZ` — this matches the arithmetic used throughout both bots' handlers (`now_ts + N * 86400`, `sub_ends > now_ts`, ...). Conversion happens in the SQL itself (`to_timestamp($1)` / `EXTRACT(EPOCH FROM ...)::bigint`), not in Python.

The `users` table's `id` (UUID primary key) and columns like `remnawave_uuid`/`merged_into` are schema-ready for a planned identity rework (letting a person exist without a `telegram_id`) that **hasn't landed in application code yet** — every current call site still looks users up by `telegram_id`, and `vpn_service._panel_username()` is still `str(telegram_id)`. Don't assume `id`/`remnawave_uuid`/`merged_into` are populated or read anywhere yet; completing that rework is Phase 4.

**`remnawave/`** — one async panel client (`RemnawaveClient`), used by both bots. It handles either auth mode: a static `REMNAWAVE_TOKEN`/`REMNAWAVE_API_KEY` (interchangeable aliases), or `REMNAWAVE_USERNAME`+`REMNAWAVE_PASSWORD` login with a cached token and one automatic re-login on a 401. A 401 against a *static* token is a config error and surfaces instead of retrying. HTTP failures are normalized onto an error hierarchy — catch `UserNotFoundError` rather than matching on message strings.

Note `remnawave_api` (the SDK this project imports, for its request/response models) and `remnawave` (a separate, similarly-named package, **not** a dependency here) are different packages — don't confuse them when reading docs.

**`settings.py`** — one `pydantic-settings` model over the root `.env`, reached via `get_settings()`. Every field is optional; entrypoints assert what they need with `settings.require("user_bot_token", ...)`. `ADMIN_IDS` is deliberately stored as a raw string and split in the `admin_ids` property: typing it as `list[int]` makes pydantic-settings JSON-decode the env value before any validator runs, which crashed the bot on a plain `ADMIN_IDS=1,2`.

**`squads.py`** — internal-squad placement. New users go into the first squad under `INTERNAL_SQUAD_MAX_USERS`; when all are full, the next `internal-N` is created (numbering continues from the highest existing name, not the count) copying inbounds from an existing squad.

### admin_bot structure

- **Authorization is a middleware, not a per-handler call.** `app/middlewares/admin_auth.py` is attached to the admin router in `app/handlers/admin/router.py`, on both the `message` and `callback_query` observers. Handlers below it can assume the caller is an admin. Don't add `check_admin_access` calls back into handlers, and if you add a new admin router, include it under that same parent router so it inherits the check.
- **Paginated lists share one implementation.** `app/handlers/admin/pagination.py` owns the nav keyboard, item pickers, page parsing, and the "go to page N" prompt. A list view registers a `PagedView`, which is what lets one shared handler render any of them. Use it rather than hand-rolling prev/next arithmetic.
- `app/handlers/admin/users/` is split by flow (`create`/`edit`/`delete`/`search`/`stats`) over a shared `common.py`.

### user_bot structure

`handlers/setup.py` drives all per-device setup instructions from one `PLATFORMS` table of `PlatformSpec`s plus two generic handlers (`os:*` and `manual_setup:*`). To add a device, add a table entry and a button in `os_keyboard()` — a test asserts those two stay in sync.

`app/services/remnawave/vpn_service.py` is async throughout and awaits the repositories directly.

### Payments

YooKassa. `user_bot/payments/yookassa_client.py` creates payments; `user_bot/payments/webhook.py` receives the success callback. **The webhook has no signature of its own from YooKassa** — the only trustworthy signal is a server-to-server re-fetch of the payment by ID (`fetch_payment`). The handler must never credit a subscription/gift code based on the raw request body (`event`/`status`/`metadata`) alone, only on a verified fetch's own result — this was a real, previously-shipped vulnerability (forgeable free subscriptions), not a hypothetical one, so don't reintroduce a code path that trusts the request body. `user_bot/tests/test_webhook_security.py` guards both halves of it.

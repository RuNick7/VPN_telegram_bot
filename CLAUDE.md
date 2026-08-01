# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two independent Telegram bots for a VPN-subscription service (Remnawave panel + YooKassa payments), a shared package holding everything both bots need, and a Go backend for the customer website:

- `admin_bot/` — operator-facing aiogram bot: manage Remnawave users/hosts/nodes/squads, promo codes, broadcasts, node/squad monitoring, backups. Entrypoint `admin_bot/main.py`.
- `user_bot/` — customer-facing aiogram bot: signup, subscription purchase via YooKassa, referrals, promo codes, device setup instructions. Two runtime entrypoints against the same codebase: `user_bot/bot.py` (long-polling) and `user_bot/run_webhook.py` (aiohttp server receiving YooKassa payment webhooks at `/webhook-yookassa`).
- `shared/` — installable package (`tgvpn-shared`, imported as `tgvpn_shared`) holding the Postgres repository layer, the Remnawave client, the settings model, and squad-placement logic. See Architecture below.
- `web/` — customer web cabinet, **Go**: JSON API plus the site itself, on one origin. Replaced the FastAPI + static-JS MVP outright. Entrypoint `web/cmd/server`. See `web/README.md`.

The overhaul is running in strictly sequential phases, each tested and deployed before the next begins. Phase 0 (webhook security fix), Phase 1 (SQLite → Postgres, Docker), and Phase 2 (this refactor) are done. Comments referencing "Phase N" mean this sequence.

**Two numbering schemes collide in this repo.** The original master plan's Phase 3 is the Go website and its Phase 4 is a continuous security audit. Separately, the FREE-tier/LTE-quota work shipped later also took the name "Phase 3" (see `docs/phase3-free-lte-rollout.md`), and comments in `migrations/0001_init.up.sql` and `vpn_service._panel_username` call the identity rework "Phase 4". When a comment says "Phase 4", it means the identity rework, not the audit.

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

The website is a separate Go module with its own suite, plus a small Node one for
the frontend's pure helpers:
```bash
cd web && go test ./...
cd web && node --test jstest/
```
`web/package.json` exists only to mark `frontend/assets/js` as ES modules so the
Node runner can import the same files the browser loads. There is no build step
and no dependency tree.

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

**Identity is `users.id` (UUID), not `telegram_id`.** A person can exist, hold a subscription and pay with no Telegram account at all — that is what the website needs. `shared/tgvpn_shared/identity.py` owns the two decisions this rests on: what a user is called in the panel, and what merging two accounts produces.

- **Panel naming.** New accounts are named `u-<uuid16>` (`panel_username_for`). Accounts created before the rework are named `str(telegram_id)` and are **never renamed** — a bulk rename against a live panel is not worth the risk. `vpn_service.resolve_panel_user` tries the stored `remnawave_uuid`, then `remnawave_username`, then the legacy name, and backfills the first two on a legacy hit, so that path retires one user at a time.
- **Payments** carry both `user_id` (ours) and `telegram_id` in YooKassa metadata. The webhook prefers `user_id`: it is the only handle a website account has, and `get_user_by_uuid` follows `merged_into`, so a payment started before a merge still credits the surviving row.
- **Merging.** `t.me/<bot>?start=link_<token>` is the handshake; `user_bot/handlers/account_link.py` is the bot end. The Telegram-side row survives (because `promo_usage.telegram_id` still references `users(telegram_id)`), and **days add up** — remaining time from both sides, summed onto now. The absorbed row keeps `merged_into` set; its leftover panel profile is expired, or adopted when the survivor had none.

`promo_usage` is keyed by `users.id` too, so a website account can redeem codes — that is what makes gift *links* possible (`settings.gift_link`), alongside the code you paste into the bot. Both routes redeem the same code, so a gift is still single-use. `telegram_id` survives on the row for support to recognise, but nothing keys on it. Still Telegram-only: admin_bot's operator table, which is correct — operators only ever arrive from Telegram.

**`remnawave/`** — one async panel client (`RemnawaveClient`), used by both bots. It handles either auth mode: a static `REMNAWAVE_TOKEN`/`REMNAWAVE_API_KEY` (interchangeable aliases), or `REMNAWAVE_USERNAME`+`REMNAWAVE_PASSWORD` login with a cached token and one automatic re-login on a 401. A 401 against a *static* token is a config error and surfaces instead of retrying. HTTP failures are normalized onto an error hierarchy — catch `UserNotFoundError` rather than matching on message strings.

Note `remnawave_api` (the SDK this project imports, for its request/response models) and `remnawave` (a separate, similarly-named package, **not** a dependency here) are different packages — don't confuse them when reading docs.

**`settings.py`** — one `pydantic-settings` model over the root `.env`, reached via `get_settings()`. Every field is optional; entrypoints assert what they need with `settings.require("user_bot_token", ...)`. `ADMIN_IDS` is deliberately stored as a raw string and split in the `admin_ids` property: typing it as `list[int]` makes pydantic-settings JSON-decode the env value before any validator runs, which crashed the bot on a plain `ADMIN_IDS=1,2`.

**`squads.py`** — which of three squads a user belongs in: **paid** (`PAID_SQUAD_NAME`, default `internal`), **FREE**, **LTE**. None of them is about capacity — they describe entitlement, and load is spread by balancers in front of the nodes. Nothing here creates squads; an operator manages them in the panel, and a missing FREE or paid squad raises `SquadResolutionError` rather than degrading (a missing paid squad means paying customers get nothing, with silence as the only symptom).

Users used to be distributed across `internal-1..N` with a per-squad cap, which also required a workaround that re-read up to 200 users five seconds after creating a squad. All of that is gone.

### admin_bot structure

- **Authorization is a middleware, not a per-handler call.** `app/middlewares/admin_auth.py` is attached to the admin router in `app/handlers/admin/router.py`, on both the `message` and `callback_query` observers. Handlers below it can assume the caller is an admin. Don't add `check_admin_access` calls back into handlers, and if you add a new admin router, include it under that same parent router so it inherits the check.
- **Paginated lists share one implementation.** `app/handlers/admin/pagination.py` owns the nav keyboard, item pickers, page parsing, and the "go to page N" prompt. A list view registers a `PagedView`, which is what lets one shared handler render any of them. Use it rather than hand-rolling prev/next arithmetic.
- `app/handlers/admin/users/` is split by flow (`create`/`edit`/`delete`/`search`/`stats`) over a shared `common.py`.

### user_bot structure

`handlers/setup.py` drives all per-device setup instructions from one `PLATFORMS` table of `PlatformSpec`s plus two generic handlers (`os:*` and `manual_setup:*`). To add a device, add a table entry and a button in `os_keyboard()` — a test asserts those two stay in sync.

`app/services/remnawave/vpn_service.py` is async throughout and awaits the repositories directly.

### web/ structure (Go)

Standard layout: `cmd/server` wires everything, `internal/` holds the pieces — `config` (reads the same root `.env`), `store` (pgxpool, the only route to Postgres), `auth` (magic links, sessions, Telegram HMAC), `account` (coordinates DB + panel), `panel` (narrow Remnawave client), `yookassa`, `pricing`, `quota`, `mailer`, `api`, `static`. `frontend/` is the site, compiled in with `go:embed`.

Two invariants are enforced structurally rather than by discipline:

- **`store` has no way to update a payment's status.** Only the Python webhook may move a payment out of `pending`, because only it re-fetches the payment from YooKassa first. Go inserts pending rows and reads status; the capability to do more simply does not exist in the package.
- **There is no session-signing secret.** Sessions are opaque random tokens stored *hashed* in Postgres, so the old `JWT_SECRET=change_me` failure mode has nothing to default to. Magic-link tokens are likewise stored hashed and never returned in an API response.

- **The frontend has no inline script or style, anywhere.** `internal/static` sends a Content-Security-Policy with no `unsafe-inline` for either, so an inline `<script>`, `<style>` or `style=` attribute would silently not run — in production only. Tests in `cmd/server` assert both halves: that the policy stays strict and that the markup stays free of them. Per-element styling that genuinely varies (a progress bar's width) is written through the CSSOM from JavaScript, which `style-src` does not police.
- **The icon sprite is inlined into pages at start-up, not linked.** Chromium and WebKit do not resolve `<use href="external.svg#id">` at all and report nothing; Firefox does, which is what makes it easy to ship broken. `assets/img/icons.svg` stays the single source and `internal/static.inlineSprite` puts it into each page in place of an `<!--icon-sprite-->` marker, stripping its comments on the way.

`internal/pricing` and `internal/quota` duplicate Python logic (`user_bot/handlers/constants.py`, `utils.py`, `shared/tgvpn_shared/lte_quota.py`) because Go cannot import it. Their tests pin the values against the Python ones — edit one side alone and they fail. Same for `internal/account/deviceid.go`, which must produce the same device token as `user_bot/handlers/devices.py`.

### Payments

YooKassa. `user_bot/payments/yookassa_client.py` creates payments; `user_bot/payments/webhook.py` receives the success callback. The Go site can also create payments, with identical metadata — the webhook is the single consumer either way. **The webhook has no signature of its own from YooKassa** — the only trustworthy signal is a server-to-server re-fetch of the payment by ID (`fetch_payment`). The handler must never credit a subscription/gift code based on the raw request body (`event`/`status`/`metadata`) alone, only on a verified fetch's own result — this was a real, previously-shipped vulnerability (forgeable free subscriptions), not a hypothetical one, so don't reintroduce a code path that trusts the request body. `user_bot/tests/test_webhook_security.py` guards both halves of it.

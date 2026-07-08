# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

KairaVPN: a VPN subscription platform built on top of a Remnawave panel. Five
independent runtime services share one SQLite database and one Remnawave
panel:

| Service | Path | Stack | Purpose |
|---|---|---|---|
| `admin_bot` | `admin_bot/` | aiogram 3, APScheduler | Telegram admin panel: users, promo codes, hosts/nodes/squads, broadcasts, monitoring, backups |
| `user_bot` | `user_bot/` | aiogram 3 (polling) | Public-facing Telegram bot: subscriptions, payments, referrals, gifts, LTE add-ons |
| webhook | `user_bot/run_webhook.py` | aiohttp | Standalone process that only receives YooKassa payment webhooks |
| `web-api` | `web/backend/` | FastAPI, uvicorn | REST API for the web cabinet (auth, subscription, payments, push) |
| `web` (frontend) | `web/frontend/` | Next.js 15 (App Router), React 19, Tailwind v4 | Cabinet UI + landing + PWA |

The root [README.md](README.md) (in Russian) is the canonical operations doc —
local dev setup, staging strategy, production deploy, and troubleshooting are
all covered there in depth. This file focuses on orientation for code changes.

## Sources of truth (read this before touching data flows)

- **Remnawave panel** (external service, `REMNAWAVE_BASE_URL`) owns VPN
  account state: UUID, inbounds, squads, live traffic/expiry as far as the
  panel is concerned. All four backend services talk to it directly — there
  is no shared cache.
- **`user_bot/data/subscription.db`** (SQLite, path via `DB_PATH` /
  `USER_BOT_DB_PATH`) owns everything Telegram/business-specific: telegram_id,
  email, referrals, promo codes, LTE quotas, payment records. `admin_bot`,
  `user_bot`, the webhook process, and `web-api` all read/write this **same
  file** — there's no ORM and no migrations tool; schema is created/upgraded
  ad-hoc by `_ensure_table()` helpers (see `user_bot/data/db_utils.py`) that
  `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` for missing columns.
  Web-only tables are prefixed `web_` (see `web/backend/kairaweb/core/storage.py`)
  to avoid colliding with the bot's schema.
- **YooKassa** owns payment status; a local copy lives in the `payments`
  table, keyed by `payment_id`.
- `web-api` does not duplicate any of this — it reads/writes the same DB
  tables and the same panel as the bots, so an admin action in `admin_bot` is
  immediately visible in the web cabinet.

### Subscription expiry model (non-obvious, read before editing extend/expire logic)

Remnawave's own `expireAt` is **not** used as the real expiry. Every user's
panel `expireAt` is force-set to `INFINITE_EXPIRE_DATE` (default
`2099-12-31...`). The real countdown lives in `subscription.db.subscription.subscription_ends`
(a unix timestamp), maintained entirely by this codebase. When a local
subscription lapses, `admin_bot`'s `subscription_expire_monitor` job strips the
user's paid `internal-*`/LTE squads and demotes them into a single `FREE`
squad (limited servers) instead of relying on the panel to cut access. Paying
again promotes the user back out of `FREE` (see
`_restore_paid_squad_after_payment` in
[user_bot/app/services/remnawave/vpn_service.py](user_bot/app/services/remnawave/vpn_service.py)).
This split exists so panel-side expiry never has to be trusted or synced under
race conditions — the local DB is the single authority for "is this user
paid."

### Internal squad capacity pooling

Paid users aren't all dumped into one Remnawave squad. Squads are named
`<INTERNAL_SQUAD_PREFIX>-<n>` (default prefix `internal`); when the
highest-numbered squad hits `INTERNAL_SQUAD_MAX_USERS`, a new `-<n+1>` squad
is auto-created and new signups land there first. LTE squad membership is
never assigned at user-creation time — it's granted only by the LTE traffic
monitor when a user has a positive paid LTE balance. See
`_get_or_create_internal_squad` / `_assign_internal_squad_for_user` in
[vpn_service.py](user_bot/app/services/remnawave/vpn_service.py).

## Runtime topology / routing

Two public domains, routed by nginx (configs in [deploy/nginx/](deploy/nginx)):

- `app.<domain>` → `/api/*` to FastAPI (`127.0.0.1:8001`), everything else to
  Next.js (`127.0.0.1:3000`).
- `webhook.<domain>` → aiohttp webhook process (`127.0.0.1:8000`), hardened
  with an nginx IP allow-list for YooKassa only. **This URL is registered in
  the YooKassa dashboard and must not change** independent of the main app
  domain.
- `web-api`'s `/api/internal/*` routes (Telegram deep-link confirmation, push
  send) are only reachable from localhost — `user_bot` calls them over loopback
  using a shared `WEB_INTERNAL_SECRET` header (`X-Kaira-Internal-Secret`), and
  nginx rejects `/api/internal/*` from the public internet with a 444.

## Web auth flow

No passwords. Two linked mechanisms:

1. **Telegram deep-link**: `web-api` issues a short-lived token
   (`web_telegram_link_tokens`), the frontend opens `t.me/<bot>?start=web_<token>`,
   `user_bot` calls `web-api`'s internal endpoint to mark it confirmed with the
   telegram_id.
2. **Magic link email**: `web-api` mints a token (`web_magic_links`), emails it
   (or logs it to stdout when `EMAIL_SENDER_MODE=mock`), and exchanging it sets
   a signed JWT session cookie (`kairavpn_session`).

See [web/backend/kairaweb/services/auth.py](web/backend/kairaweb/services/auth.py),
[web/backend/kairaweb/api/internal.py](web/backend/kairaweb/api/internal.py), and
[web/backend/kairaweb/core/storage.py](web/backend/kairaweb/core/storage.py).
Session validation is a single `@app.middleware("http")` in
[web/backend/kairaweb/main.py](web/backend/kairaweb/main.py) that gates a hardcoded
list of protected path prefixes/exact paths — add new authenticated routes to
`PROTECTED_PATH_EXACT`/`PROTECTED_PATH_PREFIX` there.

## Payments flow

`user_bot/handlers/payments.py` creates a YooKassa payment with metadata
(`telegram_id`, `days_to_extend`, `purchase_type` one of plain
subscription/`lte_gb`/gift, `is_gift`). YooKassa calls back the standalone
webhook process, which re-fetches the payment from YooKassa (never trusts the
webhook body alone), branches on `purchase_type`/`is_gift` to extend the
subscription, add LTE GB, or mint a gift promo code, then best-effort sends a
web-push notification and a Telegram message. All blocking calls (YooKassa
SDK, Remnawave SDK, SQLite) are wrapped in `asyncio.to_thread` + a hard
`asyncio.wait_for` timeout — see the timeout constants and comments at the top
of [user_bot/payments/webhook.py](user_bot/payments/webhook.py). This was a
deliberate fix for event-loop-freezing bugs; don't remove the thread/timeout
wrapping when touching this file.

## Two independent Remnawave clients — don't assume they're shared

`admin_bot` and `user_bot` each have their own Remnawave HTTP client; changes
to one do not affect the other:

- [admin_bot/app/api/client.py](admin_bot/app/api/client.py) — async, built on
  the official `remnawave_api` SDK (`httpx`).
- [user_bot/app/clients/remnawave/client.py](user_bot/app/clients/remnawave/client.py) —
  sync, hand-rolled `requests` calls with explicit `(connect, read)` timeouts
  (kept sync deliberately so callers can push it into `asyncio.to_thread`).

## admin_bot code layout: `handlers/` is live, `features/` is dead code

`admin_bot/app/features/admin/{hosts,nodes,squads}/` looks like the natural
home for those features but is **not wired into the router** — it's
unreferenced scaffolding (`app/handlers/admin/router.py` imports it only in
commented-out lines). The actual, active implementation for hosts is
`app/handlers/admin/hosts_quick.py` + `app/services/hosts_manage.py`. Check
`app/handlers/admin/router.py` before assuming a `features/` module runs.

General admin_bot layering: `app/handlers/**` = aiogram routers (thin,
FSM-driven conversation flow) → `app/services/**` = business logic + Remnawave
calls → `app/db/repo/**` / `app/db/sqlite.py` = aiosqlite access to
`subscription.db`. `app/scheduler/jobs/**` are APScheduler jobs registered in
[app/scheduler/setup.py](admin_bot/app/scheduler/setup.py): daily Remnawave
backup (03:00), daily `subscription.db` backup (17:00 MSK), node/squad
monitor, inactive-user cleanup (04:30 MSK), LTE traffic monitor, and the
subscription-expire monitor described above — all on intervals/cron set from
`.env`.

## Setup & commands

Python 3.12+ for the web backend, 3.10+ for the bots; Node.js 20 LTS for the
frontend. Config is a single root `.env` (copy from
[.env.example](.env.example)) — nearly every module loads it via
`python-dotenv` by walking up to the repo root, so there is one shared source
of secrets for all five services.

```bash
# one-time setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill it in

# admin_bot (aiogram polling)
.venv/bin/python admin_bot/main.py

# user_bot (aiogram polling)
.venv/bin/python user_bot/bot.py

# YooKassa webhook receiver (aiohttp, separate process)
.venv/bin/python user_bot/run_webhook.py

# web-api (FastAPI) — needs its own venv (Python 3.12) if system default differs
cd web/backend && python3.12 -m venv .venv312 && source .venv312/bin/activate
pip install -r requirements.txt
uvicorn kairaweb.main:app --host 127.0.0.1 --port 8001 --reload

# web frontend (Next.js)
cd web/frontend && npm ci && npm run dev      # http://127.0.0.1:3000
```

Frontend lint/build:

```bash
cd web/frontend
npx tsc --noEmit     # typecheck
npm run lint         # next lint
npm run build         # next build (production build)
```

There is **no automated test suite** in this repo (no pytest/unit tests,
no frontend test runner configured). The project's pre-deploy smoke check is
an import/build sanity pass, not real tests:

```bash
# backend imports cleanly (catches missing/broken env-dependent wiring)
cd web/backend
JWT_SECRET=test YOOKASSA_SHOP_ID=test YOOKASSA_SECRET_KEY=test \
REMNAWAVE_BASE_URL=https://example.com \
.venv312/bin/python -c "from kairaweb.main import app; print(len(app.routes))"

# frontend typechecks and builds
cd web/frontend && npx tsc --noEmit && npx next build
```

When changing bot/backend logic, prefer manually exercising the relevant
flow (see README.md section 6 "Тестирование перед продом" for the full
manual checklist: signup → Telegram link → magic link → cabinet → payment →
push) over assuming correctness from a clean import.

## Deployment

Production runs all five services as systemd units (see
[deploy/systemd/](deploy/systemd)) behind nginx with two separate TLS domains
(app + webhook, see above). Full deploy/staging/rollback instructions are in
[deploy/README.md](deploy/README.md) and the root [README.md](README.md)
section 7. Do not change ports or the webhook domain without checking those
docs — the webhook URL is hardcoded in the YooKassa dashboard.

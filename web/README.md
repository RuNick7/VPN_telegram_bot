# Customer website backend (Go)

JSON API for the customer cabinet. Replaces the FastAPI + vanilla-JS MVP that
used to live here, which had no database access of its own — it shelled out to
`python -c "import user_bot..."` once per request — and kept sessions, magic
links and rate-limit counters in in-memory dicts, so every restart logged
everyone out and a second instance could never be run.

The frontend is not here yet. This serves JSON only; static files are served by
whatever sits in front of it.

## Running

```bash
docker compose --profile web up -d web
```

Or locally, with a reachable Postgres:

```bash
cd web && go run ./cmd/server
```

Configuration comes from the repo-root `.env` — the same file the bots read.
Real environment variables always win over the file.

### Required settings

The server **refuses to start** without these:

| Variable | Why it is required |
|---|---|
| `DATABASE_URL` | — |
| `WEB_BASE_URL` | Magic links are built from it |
| `SMTP_HOST`, `SMTP_FROM` | See below |
| `REMNAWAVE_BASE_URL` + a credential | — |

SMTP is required rather than optional on purpose. The previous backend's only
implemented sender was a mock, and it returned the magic-link token in the API
response whenever that mock was active — so "email verification" verified
nothing and anyone could claim any address. A sender that cannot reach a real
mailbox must fail, not fall back.

Optional: `SMTP_PORT` (587), `SMTP_USERNAME`/`SMTP_PASSWORD`, `SMTP_STARTTLS`
(true; set false for implicit TLS on 465), `WEB_LISTEN_ADDR` (`:8080`),
`WEB_SESSION_TTL_HOURS` (720), `WEB_MAGIC_LINK_TTL_MINUTES` (15).

Login via Telegram is enabled by `USER_BOT_TOKEN` — the widget is signed with
the bot's own token. Payments need `YOOKASSA_SHOP_ID` + `YOOKASSA_SECRET_KEY`.
Both are optional; a missing one disables that feature rather than the site.

There is deliberately **no session-signing secret**. Sessions are opaque random
tokens stored hashed in Postgres, so the bug this project shipped before — a
JWT secret defaulting to `change_me` with no startup check — has nothing to
default to.

### Migration

`migrations/0005_web_auth` adds `web_sessions`, `magic_link_tokens` and
`auth_rate_limits`. Applied by the existing `migrate` service.

## Endpoints

Session cookie is `__Host-session`: HttpOnly, Secure, SameSite=Lax.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/health` | pings Postgres |
| `GET` | `/api/config` | which login routes and features are on |
| `POST` | `/api/auth/magic-link` | `{email}` → always the same answer |
| `POST` | `/api/auth/verify` | `{token}` → sets the session cookie |
| `POST` | `/api/auth/telegram` | login-widget payload, HMAC-checked |
| `POST` | `/api/auth/logout` | |
| `GET` | `/api/me` | |
| `PATCH` | `/api/me/email` | |
| `GET` | `/api/subscription` | status, expiry, connection link |
| `POST` | `/api/subscription/reset-link` | rotates the link |
| `GET` | `/api/devices` | |
| `DELETE` | `/api/devices/{id}` | one device |
| `GET` | `/api/traffic` | whitelist-traffic balance |
| `GET` | `/api/plans` | priced at the caller's referral tier |
| `POST` | `/api/payments/subscription` | `{months, return_url}` |
| `POST` | `/api/payments/traffic` | `{gigabytes, return_url}` |
| `POST` | `/api/payments/gift` | `{months, return_url}` |
| `GET` | `/api/payments/{id}` | status only |
| `GET` | `/api/referrals` | |
| `PUT` | `/api/referrals/referrer` | `{tag}`, once only |
| `POST` | `/api/promo/redeem` | `{code}` |

## Rules this service works under

**Payment state belongs to the Python webhook.** The site creates payments and
records them as `pending`; it never moves one out of pending. Deciding that a
payment succeeded requires re-fetching it from YooKassa server-to-server,
because the callback carries no signature of its own — trusting its body was a
real, exploitable forgery hole, fixed in Phase 0. `internal/store` exposes no
way to update a payment's status at all, so the rule is enforced by absence
rather than by discipline.

**Prices are looked up, never accepted.** A client naming its own amount could
buy a year for a rouble. `internal/pricing` duplicates the bot's table, and its
tests pin every cell against the Python values — if either side is edited
alone, they fail.

**Devices are addressed by a hash of their HWID**, matching the bot's scheme
exactly (`internal/account/deviceid.go`), and re-resolved against a fresh
listing on every use. A hardware fingerprint is not something to publish in a
URL, and a stale ID must resolve to nothing rather than to whichever device has
since taken that slot.

## What is not done

- **Account merging.** Someone who registers by email gets a `users` row with
  `telegram_id` NULL. Linking a Telegram account onto it afterwards is the
  identity rework — the `merged_into` column exists for it and is still unused.
  Until then such an account cannot pay or redeem promo codes: the webhook
  credits by `telegram_id`, and `promo_usage` is keyed by it. Both endpoints
  say so plainly rather than failing on a constraint violation.
- **No trial for web registrations.** The bot grants 30 days on `/start`, tied
  to a Telegram account. Granting the same per email address would be a trial
  per mailbox, so a web-registered profile is created already expired. Worth
  revisiting as a product decision.
- **Frontend.** Static files, served separately.

# Customer website backend (Go)

JSON API for the customer cabinet. Replaces the FastAPI + vanilla-JS MVP that
used to live here, which had no database access of its own — it shelled out to
`python -c "import user_bot..."` once per request — and kept sessions, magic
links and rate-limit counters in in-memory dicts, so every restart logged
everyone out and a second instance could never be run.

It now also serves the site itself. The API and the pages share one origin,
which is the reason there is no CORS policy anywhere: the session cookie is
`__Host-` prefixed and same-site, and there is no cross-origin surface to get
wrong. See [Frontend](#frontend).

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

### Checking that mail actually sends

```bash
cd web && go run ./cmd/server -check-smtp you@example.com
```

Sends one test message and exits, starting nothing else — no database, no panel
client, no listener — so it is usable before the rest of the deployment exists.
The startup check only asserts that `SMTP_HOST` and `SMTP_FROM` are non-empty;
everything that decides whether mail *arrives* (a port paired with the wrong TLS
mode, a key pasted with a trailing space, a sending domain the provider has not
verified, an outbound port the hosting company blocks) otherwise surfaces as a
customer who never got their login link — and, with no password to fall back on,
cannot get into their account at all.

On failure it names the setting to change rather than echoing a bare `535`. The
password is never printed, only its length, which is what makes a truncated
paste visible.

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
| `GET` | `/auth/telegram` | where the widget redirects; same check, answers with a redirect |
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

## Frontend

`frontend/` — plain HTML, one stylesheet, ES modules. No framework, no build
step, no `node_modules`: the whole site is about 12 KB of markup and script
before compression, and a bundler would have weighed more than the thing it
bundled. It is compiled into the binary with `go:embed`, so a deployment is one
artefact and there is no directory the server can be pointed at by mistake.

`internal/static` loads it at start-up: every file gets a strong ETag, text
files get a gzip copy, and the route table is fixed. Nothing is read from disk
while serving, so no request can influence a filesystem path.

**The Content-Security-Policy has no `unsafe-inline` in it**, for scripts or for
styles. That is a constraint the markup was written to satisfy rather than a
header bolted on afterwards: there is not one inline `<script>`, `<style>` or
`style=` attribute in the site, and a test asserts it stays that way. The one
third-party script — Telegram's login widget — is admitted only when Telegram
login is actually configured, and is used in redirect mode specifically so that
`unsafe-eval` is not needed for it.

Everything else is served from this origin too. Inter and JetBrains Mono are
self-hosted rather than loaded from Google Fonts, and the icons are an SVG
sprite rather than an icon font from a CDN — for a service sold to people whose
networks block things, a customer who cannot reach `fonts.googleapis.com`
should still get a working page instead of the words "person" and "devices"
where the icons belong.

The sprite is **inlined into each page** by `internal/static`, not linked.
Chromium and WebKit do not resolve `<use href="external.svg#id">` at all — they
render nothing and log nothing, while Firefox renders it correctly, which is
what makes the mistake easy to ship. Inlining server-side keeps one copy of the
sprite in the repository instead of nine that drift.

QR codes are generated in the browser by `assets/js/qr.js`, written out rather
than taken from npm for the same CSP reason. Its tests check the Reed-Solomon
stage against the worked example in ISO/IEC 18004 Annex I and read the finished
matrix back — a wrong QR code looks exactly like a right one, so "it rendered"
proves nothing.

Cache policy follows how often a file can change: fonts, images and video are
`immutable` for a year because a new one means a new filename. HTML, CSS and
JavaScript all revalidate, which a matching ETag answers with a bodyless 304 --
and they revalidate on the *same* terms deliberately, because they change
together. A `max-age` on scripts alone once left returning visitors running the
previous JavaScript against current markup for ten minutes after a deploy, with
nothing observable to explain it. A first visit to the landing page is ~136 KB
gzipped, 117 KB of which is the two typefaces; every page after that is ~30 KB
and mostly 304s.

The background video is decoration on top of a poster that is already in place,
so it is only fetched on a wide screen, and never when the visitor has asked for
reduced motion or turned on a data saver. Phones get the still.

### Tests

```bash
cd web && go test ./...    # includes the real embedded site
cd web && node --test jstest/
```

The Go suite checks the frontend as shipped, not just the handler: that every
route renders, that every asset and icon a page references exists, that no page
carries inline script or style, and that nothing loads from a Google origin.

## What is not done

- **No fingerprinted asset filenames.** CSS and JavaScript revalidate on every
  navigation instead of being cached outright. It costs one conditional request
  each, answered 304 with no body; hashing the names would let them be cached
  outright *and* stay correct, but needs a build step, which is the thing this
  frontend is deliberately without.
- **Search-engine niceties.** No `sitemap.xml`, no `robots.txt`. The cabinet is
  `noindex` already; the landing page is the only thing worth indexing.

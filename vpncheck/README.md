# vpncheck

Connects to every server in a subscription the way the customer's app does,
and writes a log per server. One self-contained binary per platform: Xray is
compiled in, nothing to install. Its own messages are in Russian, since
customers run it too.

What it checks, per server:

1. DNS, the TCP port, and TLS where the server has it (certificate, issuer).
2. The tunnel itself: a real Xray client with the outbound taken from the
   subscription (VLESS raw/gRPC/XHTTP/WS/HTTPUpgrade with REALITY or TLS,
   Hysteria2, Trojan, Shadowsocks, VMess; `dialerProxy` chains too).
3. Through the tunnel: pings, the exit country and data centre, and with
   `-speed` a download.

A failing server gets a cause in plain words ("the server did not recognise
the client", "the node does not know this user", ...) next to Xray's own log.

## Output

Every run writes `vpncheck-logs/<date_time>/`:

| file | what |
|------|------|
| `summary.txt` | one line per server, then the details of the failures |
| `report.txt` | the summary plus every server's log, capped at 9 MB: this is what goes to support |
| `summary.json` | the same, for scripts |
| `servers/NN_host_port_kind.log` | one server: the steps, its outbound, the whole Xray log |

Each server's tunnel runs in a process of its own (the same binary, started
again), so its Xray log holds that server's lines only: Xray's gRPC client
goes on redialling a dead server after its instance is closed, and in one
process those retries ended up in every later server's log.

**Secrets are cut from every file.** User UUIDs, passwords, REALITY public
keys and short IDs and the subscription token are replaced
with `[скрыто:…]`, consistently within a run so lines can still be matched up.
The machine's own address in Xray's connection lines becomes `[мой адрес]`,
and the hostname is never recorded, only the OS and architecture.

## Running it

Switch the VPN app off first: the check is meaningless through another
tunnel, and it warns when it sees one.

```
vpncheck https://sub.example.com/api/sub/XXXX         check a subscription
vpncheck -send https://sub.example.com/api/sub/XXXX   check and send the report to support
vpncheck                                              ask what to check (what a double-click does)
```

Useful flags: `-only de1` (servers whose address or profile contains `de1`),
`-list` (show the servers, check nothing), `-speed 20` (download 20 MB through
each), `-timeout 15s`, `-sub` repeatable or a file, `-out DIR`, `-note TEXT`
(with `-send`: what does not work). `-h` lists them
all. Exit code 0 means every server works, 1 that some don't, 2 that the run
could not happen (bad arguments, nowhere to save).

### Linux server

```bash
curl -LO https://<download>/vpncheck-linux-amd64 && chmod +x vpncheck-linux-amd64
./vpncheck-linux-amd64 -speed 20 https://sub.example.com/api/sub/XXXX
```

Cron-friendly: no prompts unless it is started with no arguments.

### macOS

Download `vpncheck-macos-arm64` (Apple silicon) or `vpncheck-macos-amd64`
(Intel). The binary is not notarised, so Gatekeeper blocks it once:

```bash
xattr -d com.apple.quarantine vpncheck-macos-arm64
chmod +x vpncheck-macos-arm64
./vpncheck-macos-arm64
```

### Windows

Download `vpncheck-windows-amd64.exe` and double-click it, or run it from
PowerShell with arguments. SmartScreen may ask once ("More info", then "Run
anyway"). Started by double-click, it asks for a link and waits for
Enter before the window closes.

### The customers' app: vpncheck-app

The same check behind a page, for customers who should not meet a terminal:
one field for the subscription link, a button to check, and buttons to send,
save or copy the report. `cmd/vpncheck-app` starts it, `internal/app` is the page
and everything behind it. For now the page opens in the browser; the window
stays open beside it while a check runs, and the app exits a few minutes
after the page is closed.

- **The subscription link is the only input.** No codes. A link on another
  host than the ones built in (`DOMAINS`, default `sub.kairavpn.pro`) is
  turned away with an explanation, as are an expired subscription, a device
  limit, and a page that is not a subscription. The link is remembered in the
  user's config directory (`vpncheck/subscription`, mode 0600) until
  «Забыть ссылку».
- **What the customer sees** is the subscription card (name, traffic, and
  whether it is paid), the servers grouped by profile with a dot each, and a
  line saying which ones do not work. A server opens into the same steps and
  Xray log the report holds.
- **Payment status comes from the site** (`/api/vpncheck/status`, asked
  while the subscription loads), not from the panel's date, which with the
  free tier on is ten years out for everyone. An expired subscription is not
  checked at all: the app says so and offers «Продлить», a link to the
  site's plans. The free tier is said on the card, since only some servers
  are open to it. When the site does not answer, the check goes on and the
  card says payment could not be confirmed.
- **«Отправить в поддержку»** sends the report, with an optional line of the
  customer's own words, into their open ticket, or opens «Проверка
  серверов»; see Sending a report to support below.
- **Reports** are kept in the user's cache directory, the last ten runs.
  For a customer without a ticket in mind, «Сохранить отчёт» puts a zip of the run into Downloads and shows it in the
  file manager; «Скопировать файл» puts the same zip on the clipboard as a
  file, to paste into a Telegram chat with support.
- **Only this computer can reach it.** It listens on 127.0.0.1 on a free
  port, every API call carries a token generated at start (handed to the page
  in the URL fragment, never sent to a server), the Host header must be
  127.0.0.1 so a DNS-rebinding page cannot talk to it, and the page has no
  inline script or style under a strict CSP.

On a Mac it ships as a zip (`vpncheck-app-macos-*.zip` holding
`KairaVPN-Check`), because a bare binary loses its executable bit on download
and opens in TextEdit. Unsigned, so the first start is blocked once: System
Settings → Privacy & Security → «Open Anyway».

`go test ./internal/app` runs it end to end against a fake panel and real Xray
nodes. `TestDemo` serves it on a fixed address with made-up servers, for
looking at the page:

```bash
VPNCHECK_DEMO=127.0.0.1:8765 go test ./internal/app -run TestDemo -v -timeout 1h
# then open http://127.0.0.1:8765/#k=demo
```

With `VPNCHECK_DEMO_SITE=http://127.0.0.1:8080` it asks a running `web/` for
the status and sends reports there; that site's panel must know the demo
link's short UUID (`SayZcYcdx7zRHfxe`).

### Not covered

Phones. The tool runs on a computer or a server; for a phone-only problem,
support can ask for the Happ app's own logs as an attachment.

## Sending a report to support

Nothing leaves the computer until the customer sends it: «Отправить в
поддержку» in the app, `-send` on the command line, or «да» to the question a
double-clicked `vpncheck` asks once the report is written (and can be read).

1. The program sends `report.txt`, the one-line summary and the customer's
   note, if any, to the site (`POST /api/vpncheck/report`) with the
   subscription link.
2. The site asks the panel whose subscription that is and finds the customer
   from it. The link is the only authorisation: whoever holds it already uses
   that VPN, and all it allows is a message in that customer's own ticket.
   The site never fetches the link, and cuts its identifier out of the
   report once more in case an old build left it in.
3. The report lands as the customer's message in their latest open ticket,
   or opens «Проверка серверов», and reaches the admins like any other. The
   answer comes to the bot and the cabinet.

A few reports per customer a day are taken. An operator can ask for one with
«🩺 Запросить логи» on the ticket card: the customer gets the download link
and these steps as an answer in the ticket. Without the site (or Telegram as
the only channel) «Скопировать файл» still puts the report on the clipboard
for the support chat.

## Device limits

The panel's device limit (HWID) applies: the subscription is fetched with
vpncheck's own device id, kept in the user's config directory, so a computer is
one device however often it runs. It shows up in the customer's device list
as "vpncheck" and can be removed there. A customer at their limit needs to free
a slot first.

## Covering FREE and LTE

A subscription only holds the servers its owner is entitled to. To check every
squad from a server, keep one test account per tier (paid, FREE, LTE) and pass
all three: `-sub URL1 -sub URL2 -sub URL3`.

## The nodes' side: vpncheck-agent

A report shows what the customer's computer saw. What the node saw is in the
node's own Xray logs, and the panel's API does not expose them, so each node
runs a small agent that admin_bot asks.

Every run sends one request through each server to a host named after the
run, `vpncheck-<run>-<NN>.invalid`; the report prints it per server with the
time the node saw the run, in UTC and corrected against Cloudflare's clock.
`.invalid` never resolves, so the request goes nowhere, but the node's access
log records it with the user it authenticated and the address it came from.
When a customer's report reaches the admin chats, admin_bot sends every agent
those windows. Each agent finds the marker, takes the user and address from
that line, and returns that user's lines and the error lines naming that
address within the window. admin_bot replies to the ticket card with one file
covering all the nodes.

- Nothing goes into the ticket: the node lines hold the customer's address,
  and the ticket is something the customer reads.
- A server that refused the client (a wrong REALITY key, a Hysteria2
  password it does not know) never learns the user, so there is no marker
  line. For a failed server the agent then returns the node's error lines
  from that time, marked as possibly about other customers.
- The agent answers only over TLS with its own self-signed certificate,
  which admin_bot pins, and only to the token it generated on first start.
  It prints both as the line for `NODE_LOG_AGENTS`.

```
vpncheck-agent -name de1 -public de1.example.net     # :7443, logs in /var/log/remnanode
vpncheck-agent -print                                 # the NODE_LOG_AGENTS line again
```

Flags: `-log` (repeatable; the agent also reads `<log>.1`, the copy
logrotate leaves), `-tz` (the zone Xray writes its times in, UTC in the
remnanode container), `-listen`, `-data` (token and certificate, default
`/var/lib/vpncheck-agent`). Installing it on a node, with the Xray log
settings it needs: `docs/support-tickets-rollout.md`, step 6.

## Daily check for operators

The same binary, run by an operator, asks the agents itself: each server in
the report then carries the node's lines for that check under the client's
Xray log, and the summary says which node served it and which nodes did not
answer. `-env` points at the bot's `.env` for `NODE_LOG_AGENTS`,
`ADMIN_BOT_TOKEN` and `ADMIN_IDS`; `-notify` sends the one-line result and
`report.txt` to every admin chat through admin_bot; `-keep N` deletes runs
older than N days from `-out`.

```bash
vpncheck -env /opt/tg_vpn/.env -notify -keep 30 \
  -sub https://sub.example.com/api/sub/PAID -sub https://sub.example.com/api/sub/FREE
```

Agents only answer the address port 7443 is open to, which is the bot's
server, so that is where the daily run goes. As a systemd timer there:

```ini
# /etc/systemd/system/vpncheck-daily.service
[Unit]
Description=vpncheck: daily check of every server
After=network-online.target

[Service]
Type=oneshot
# The device id lives in the config directory; without one, every run would
# be a new device in the panel and the test accounts would hit their limit.
Environment=XDG_CONFIG_HOME=/var/lib/vpncheck
StateDirectory=vpncheck
ExecStart=/usr/local/bin/vpncheck -env /opt/tg_vpn/.env -out /var/lib/vpncheck/reports -notify -keep 30 \
  -sub https://sub.example.com/api/sub/PAID -sub https://sub.example.com/api/sub/FREE
# 1 means a server failed: a result for the chat, not a failed unit.
SuccessExitStatus=1
```
```ini
# /etc/systemd/system/vpncheck-daily.timer
[Timer]
OnCalendar=*-*-* 07:00
Persistent=true

[Install]
WantedBy=timers.target
```
```bash
systemctl daemon-reload && systemctl enable --now vpncheck-daily.timer
systemctl start vpncheck-daily.service     # one run now
```

From a computer at home the check sees what customers' providers do to the
traffic, which a data centre does not. Node lines come with it only if that
computer's address is allowed to port 7443 too; give the agents with
`-agents` (the `NODE_LOG_AGENTS` value) or `-env` a copy of the `.env`.

Node lines hold the address the check came from, so they are added only to an
operator's run: a customer's run never asks the agents, and a run that has
them is never sent to a ticket.

**Balancers.** Happ gets each profile as a balancer over several servers, and
its log names the balancer, so it shows less than a connection to one server
would. vpncheck takes every server out of the balancers and connects to each
one directly, with its own full Xray log; the profiles a server belongs to are
listed next to it. When an address is itself shared by several nodes, the
node lines say which one served the check. What it does not reproduce is the
balancer's own choice of server.

## Building

```bash
./build.sh                                    # version from git, site from WEB_BASE_URL in ../.env
VERSION=1.0.0 SITE=https://example.com ./build.sh
```

Writes into `dist/`, with `SHA256SUMS`: `vpncheck-*` and `vpncheck-app-*` for
Linux, macOS and Windows, each for amd64 and arm64; the macOS app zipped as
`vpncheck-app-macos-*.zip`; and `vpncheck-agent-linux-*` for the nodes. The
site is compiled into both, so sending needs no flags (`-site` overrides it
for `vpncheck`), and the subscription hosts into the app (`DOMAINS=a,b`).
Without Go, in Docker:

```bash
docker run --rm -v "$PWD/..:/src" -w /src/vpncheck golang:1.26 ./build.sh
```

Host `dist/` anywhere customers can download from and set
`VPNCHECK_DOWNLOAD_URL` to it: see `docs/support-tickets-rollout.md`.

## Tests

```bash
go test ./...
```

`internal/check` starts real Xray servers on 127.0.0.1 (VLESS raw, REALITY
over raw/gRPC/XHTTP, Hysteria2) and checks the tool both gets through and
explains why it does not with a wrong key or password, and that the node logs
the marker next to the user. `internal/nodelog` pins the search on sample
logs.

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

**Secrets are cut from every file.** User UUIDs, passwords, REALITY public
keys and short IDs, the subscription token and the support code are replaced
with `[скрыто:…]`, consistently within a run so lines can still be matched up.
The machine's own address in Xray's connection lines becomes `[мой адрес]`,
and the hostname is never recorded, only the OS and architecture.

## Running it

Switch the VPN app off first: the check is meaningless through another
tunnel, and it warns when it sees one.

```
vpncheck https://sub.example.com/api/sub/XXXX     check a subscription
vpncheck ABCD-EFGH-JKLM                           check and send the report to a support ticket
vpncheck                                          ask what to check (what a double-click does)
```

Useful flags: `-only de1` (servers whose address or profile contains `de1`),
`-list` (show the servers, check nothing), `-speed 20` (download 20 MB through
each), `-timeout 15s`, `-sub` repeatable or a file, `-out DIR`. `-h` lists them
all. Exit code 0 means every server works, 1 that some don't, 2 that the run
could not happen (bad arguments, a code the site refused, nowhere to save).

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
anyway"). Started by double-click, it asks for a link or a code and waits for
Enter before the window closes.

### Not covered

Phones. The tool runs on a computer or a server; for a phone-only problem,
support can ask for the Happ app's own logs as an attachment.

## Sending a report to support

Nothing leaves the computer unless the customer agrees twice:

1. An operator presses «🩺 Запросить логи» on the ticket card in admin_bot.
2. user_bot asks the customer in Telegram, listing what is collected and what
   is not. Only on «Согласен» does it show a one-off code (72 hours) and the
   download link.
3. `vpncheck CODE` opens the ticket by that code, takes the subscription link
   from the site, runs the check, and shows where `report.txt` is.
4. It asks again: «Отправить? Введите «да» или «нет»». Only «да» uploads it; the report lands in
   the ticket as the customer's message, and the admins get it like any other.

A code is single-use and works for one ticket only; a closed ticket refuses it.
Customers without Telegram cannot be asked in the bot: they run the check
without a code and attach `report.txt` to the ticket themselves.

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

## Building

```bash
./build.sh                                    # version from git, site from WEB_BASE_URL in ../.env
VERSION=1.0.0 SITE=https://example.com ./build.sh
```

Writes six binaries and `SHA256SUMS` into `dist/`: Linux, macOS and Windows,
each for amd64 and arm64. The site is compiled in so `vpncheck CODE` needs no
flags; `-site` overrides it. Without Go, in Docker:

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
explains why it does not with a wrong key or password.

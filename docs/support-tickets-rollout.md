# Support tickets rollout

Ships **off**. Deploying the code adds five tables and changes nothing a
customer or an admin can see until `SUPPORT_ENABLED=true` is set — and one
thing outside this repository has to change first: nginx.

## What it does

A signed-in customer, subscribed or not, opens a ticket in the cabinet at
`/app/support`: a subject, a message, up to three files — pictures, video
(MP4, MOV, WebM), PDF or text. admin_bot sends it to **every `ADMIN_IDS`
chat** as a card. An admin answers by **replying** to the card, or to any
other message of that ticket, with text, a photo, a video or a document. The
customer sees the answer in the cabinet, with a dot on the support tab, and
gets a message from user_bot if their account has Telegram linked.

Under each card: close / reopen, the customer's full record, and the whole
thread. `/tickets` (or «🆘 Поддержка» in `/admin`) lists what is waiting.

## 1. Let nginx accept the uploads

nginx refuses any request body over **1 MB** by default, before it reaches
the site: a customer attaching a screenshot would get a bare 413. The site's
own limits are 45 MB a video and 50 MB a message, so allow a little more
than that. In the `server {}` block that proxies to the site:

```nginx
client_max_body_size 55m;
```

The JSON endpoints keep their own 64 KB cap inside the Go server, so raising
this for the whole site does not widen them. Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

nginx buffers the request body before passing it on, so a slow phone upload
is nginx's to wait for; the site gives upload requests ten minutes of its own
on top of that.

## 2. Deploy with the flag still off

```bash
docker compose up -d --build                      # migrate runs 0015; bots rebuilt
docker compose --profile web up -d --build web    # the site
```

With the flag off the support section answers 404, its tab stays hidden, and
admin_bot starts no delivery loop.

## 3. Switch it on

In `/opt/tg_vpn/.env`:

```
SUPPORT_ENABLED=true
```

The **same key** switches both halves, and both read it at start-up, so
recreate both. Not `docker compose restart`: that reuses the container, and
the environment a container got from `env_file` is fixed when it is created.

```bash
docker compose up -d --force-recreate bots
docker compose --profile web up -d --force-recreate web
```

Check that `ADMIN_IDS` holds the chats that should get tickets, and that each
of those admins has pressed Start in the admin bot — Telegram does not let a
bot write to someone who has never opened it. `WEB_BASE_URL` has to be the
public `https://` address for the «Открыть обращение» button in the
customer's notification.

## 4. Smoke test

1. Sign in to the site, open «Поддержка», send a ticket with a screenshot.
2. Within a few seconds the admin chat gets the card and the screenshot.
3. Reply to the card with text and a photo. The bot confirms with «✅ Ответ
   отправлен в обращение #N».
4. The cabinet shows the answer and the photo; the tab has a dot until the
   ticket is opened. A customer with Telegram linked also gets a message from
   user_bot.

## 5. Server check reports (vpncheck)

Optional, on top of tickets. With it, a customer runs «KairaVPN Проверка»
(`vpncheck-app`, or the `vpncheck` command line; see `vpncheck/README.md`),
pastes their subscription link and presses «Отправить в поддержку»: the
report lands in their open ticket, or opens «Проверка серверов». Nothing is
sent before that press. The app also asks the site whether the subscription
is paid, and offers «Продлить» instead of checking an expired one. user_bot's
«🩺 Проверить серверы» and the cards' «🩺 Запросить логи» stay hidden until
`VPNCHECK_DOWNLOAD_URL` is set.

1. **Migration `0016_vpncheck_reports`** runs with the rest on
   `docker compose up -d --build`; it adds one table and touches nothing else.
   The site's two new endpoints (`/api/vpncheck/status`, `/api/vpncheck/report`)
   are under `/api/`, which nginx already passes on.
2. **Build the binaries** with the site compiled in, so neither the app nor
   `vpncheck -send` needs flags (`SITE` defaults to `WEB_BASE_URL` from
   `.env`):
   ```bash
   cd vpncheck && VERSION=1.0.0 ./build.sh
   # or, without Go on the host:
   docker run --rm -v "$PWD/..:/src" -w /src/vpncheck golang:1.26 ./build.sh
   ```
3. **Host `vpncheck/dist/`** where customers can download it, for example
   from the site's nginx:
   ```nginx
   location /vpncheck/ {
       alias /opt/tg_vpn/vpncheck/dist/;
       autoindex on;
   }
   ```
   The files in it and `SHA256SUMS` are the whole release.
4. **Set the link** in `.env` and recreate the bots, which read it at
   start-up (the site does not need it):
   ```
   VPNCHECK_DOWNLOAD_URL=https://example.com/vpncheck/
   ```
   ```bash
   docker compose up -d --force-recreate bots
   ```
   The `client_max_body_size` from step 1 already covers a report (up to
   10 MB).

Smoke test: run the app, paste a test account's subscription link and check.
The card says until when it is paid. Type a line and press «Отправить в
поддержку»: the app says which ticket it went to, and the admin chat gets the
card with `vpncheck-report.txt` under it. On an existing ticket, «🩺 Запросить
логи» sends the customer the download link and these steps as an answer in
the ticket, through user_bot and the cabinet.

## 6. The nodes' side (vpncheck-agent)

Optional, on top of step 5. With it, a customer's report is followed in the
admin chat by a file with each node's Xray log lines from that check: the
customer's own connections, found by the run's marker, and for a server that
refused them, the node's errors at that time. Nothing of it goes into the
ticket. See "The nodes' side" in `vpncheck/README.md` for how it finds them.

On **each node**:

1. **Have Xray write its logs to files on the host.** In the panel, in the
   node's config profile, set the `log` section, for example:
   ```json
   "log": {
     "loglevel": "warning",
     "access": "/var/log/remnanode/access.log",
     "error": "/var/log/remnanode/error.log"
   }
   ```
   and mount that directory in the node's `docker-compose.yml`:
   ```yaml
   services:
     remnanode:
       volumes:
         - /var/log/remnanode:/var/log/remnanode
   ```
   The access log grows with traffic; rotate it daily and keep one old copy,
   which is all the agent reads (`access.log.1`):
   ```
   # /etc/logrotate.d/remnanode
   /var/log/remnanode/*.log {
       daily
       rotate 1
       missingok
       notifempty
       copytruncate
   }
   ```
2. **Install the agent** from `vpncheck/dist/` (`build.sh` builds it):
   ```bash
   install -m 755 vpncheck-agent-linux-amd64 /usr/local/bin/vpncheck-agent
   ```
   ```ini
   # /etc/systemd/system/vpncheck-agent.service
   [Unit]
   Description=vpncheck-agent: node logs for support tickets
   After=network-online.target

   [Service]
   ExecStart=/usr/local/bin/vpncheck-agent -name de1 -public de1.example.net
   DynamicUser=yes
   StateDirectory=vpncheck-agent
   # Xray creates its log files as root with mode 0600: this lets the agent
   # read them, and nothing else root could do.
   AmbientCapabilities=CAP_DAC_READ_SEARCH
   CapabilityBoundingSet=CAP_DAC_READ_SEARCH
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   systemctl daemon-reload && systemctl enable --now vpncheck-agent
   journalctl -u vpncheck-agent -n 5     # prints the NODE_LOG_AGENTS line
   ```
   `-public` is the address admin_bot reaches the node by; `-tz` is needed
   only if the remnanode container is not on UTC.
3. **Open port 7443 to admin_bot's server only**:
   ```bash
   ufw allow from <IP of the bot server> to any port 7443 proto tcp
   ```

Then on the **bot server**, put every node's line in `.env`, joined with
commas and no spaces, and recreate the bots:

```
NODE_LOG_AGENTS=de1=https://<token>@de1.example.net:7443#<fingerprint>,nl1=https://...
```
```bash
docker compose up -d --force-recreate bots
```

The bot logs `Node logs started for N agent(s).`; an entry it cannot read is
logged by name and left out. To see which log files an agent can read, on the
node itself:

```bash
curl -sk -H "Authorization: Bearer $(cat /var/lib/vpncheck-agent/token)" https://127.0.0.1:7443/v1/health
```

A file that does not exist or cannot be read is listed with the error. A reinstalled agent with a wiped
`/var/lib/vpncheck-agent` has a new token and certificate: its line in
`NODE_LOG_AGENTS` has to be replaced, and until then the file says that
node answered with the wrong certificate.

## Operating it

- **Files live in Postgres**, in `support_attachment_data`. The daily dump the
  admin bot sends over Telegram leaves that table's data out, so it stays under
  Telegram's 50 MB; restored from such a dump, a ticket's files show as expired.
  Back the database up by other means if the files matter.
- Files in tickets nobody has written in for **90 days** are deleted by the
  site's hourly sweep; the thread keeps a line naming them.
- Per customer: 3 open tickets, 10 new tickets and 40 messages an hour,
  200 MB of files a day.
- The delivery loop reports to `job_runs` as `support_outbox`, and the service
  health monitor alerts if it stops succeeding.
- A file Telegram refuses to take from the bot arrives as a line saying so,
  instead of holding up every ticket behind it.

## Turning it off

`SUPPORT_ENABLED=false` and recreate both again. The tables and their contents
stay; the section disappears. `0015_support_tickets.down.sql` drops the tables
with everything in them — only for when the history should go too.

## Privacy

A ticket's text and files are forwarded into the admins' Telegram chats, which
means they pass through Telegram's servers. The privacy policy at
`/docs/privacy` should say so before this is switched on.

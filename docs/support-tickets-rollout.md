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

Optional, on top of tickets. With it, an operator can ask a customer for a
report from `vpncheck` (see `vpncheck/README.md`) and get it in the ticket,
only after the customer agrees in Telegram and then confirms the upload in
the program. Off until `VPNCHECK_DOWNLOAD_URL` is set: no button on the cards.

1. **Migration `0016_support_diagnostics`** runs with the rest on
   `docker compose up -d --build`; it adds one table and touches nothing else.
2. **Build the binaries** with the site compiled in, so `vpncheck CODE` needs
   no flags (`SITE` defaults to `WEB_BASE_URL` from `.env`):
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
   The six files and `SHA256SUMS` are the whole release.
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

Smoke test: on a ticket from a customer with Telegram linked, press «🩺
Запросить логи». The customer gets the question from user_bot; «✅ Согласен»
gives a code and the link, and the admin chat gets a note of the decision.
Run `vpncheck CODE`, answer «да», and the report arrives in the ticket as
`vpncheck-report.txt`. A customer without Telegram cannot be asked: pressing
the button tells the operator so, and the customer attaches `report.txt`
from a run without a code.

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

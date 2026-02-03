# Admin Bot

Admin bot for managing the Remnawave panel from Telegram.  
The project is split into two parts:

- `admin_bot/` — admin bot (this repo)
- `user_bot/` — user-facing bot and the `subscription.db` database

The bot lets you manage users, promo codes, hosts, send broadcasts, view stats, and monitor node load.

---

## Features

### Users
- Create a user in Remnawave and write to `subscription.db`
- Step-by-step creation:
  - `username` (**digits only = Telegram ID**)
  - expiration (forever / month / week / default 1 day)
  - traffic limit in **GB**
  - `tag` (optional)
  - `telegram_id` (optional)
  - `hwid` limit (optional)
- Edit:
  - expiration (`expire_at`) — updates both the panel and `subscription.db`
  - `username` — updates both the panel and `telegram_id` in `subscription.db`
  - `hwid`, `tag`, traffic limit — panel only
- Delete user from both the panel and `subscription.db`

### Stats
- Total users
- Online users count
- Users table with `telegram_id` and days left
- Pagination

### Promo Codes
- Create promo codes (manual or generated)
- Types: `gift` / `days`
- Value: **number of days**
- One-time: yes/no
- Delete by code

### Broadcasts
- Send text, photo, or video to all users in `subscription.db`
- Batching and rate limiting

### Hosts
- Quick host creation with minimal parameters
- Inbound selection (pagination)
- Nodes selection (multi-select + pagination)
- Internal squad selection
- Exclude selected squad from other hosts (on request)

### Monitoring
- RAM checks (via `/api/system/stats`)
- Offline node checks
- Internal squads size control
- Anti-spam: no more than once every 5 minutes

### Backups
- Daily `subscription.db` delivery to admins at 17:00 MSK
- Auto-clean old backups (keep last 10)

---

## Project Structure

```
KairaVPN_admin_bot/
├─ admin_bot/         # admin bot
│  ├─ app/            # code
│  ├─ logs/           # logs
│  └─ main.py         # entrypoint
├─ user_bot/
│  └─ data/
│     └─ subscription.db  # users/promo DB
├─ .env               # shared config
├─ .env.example       # config example
├─ requirements.txt   # shared dependencies
└─ .venv              # Python virtualenv
```

---

## Install & Run

1) Activate the virtualenv:
```
source .venv/bin/activate
```

2) Install dependencies:
```
pip install -r requirements.txt
```

3) Copy config:
```
cp .env.example .env
```

4) Fill in `.env` (including `Admin_bot_token`)

5) Run the bot:
```
.venv/bin/python admin_bot/main.py
```

---

## Important

- **username = Telegram ID** (digits only).
- `subscription.db` is the user-bot database storing users and promo codes.
- When creating/updating a user, the **expiration** is synced to `subscription.db`.
- When `username` changes, `telegram_id` is updated in `subscription.db`.

---

## Technical Notes

- User create/edit operations use the Remnawave panel API.

---

# user_bot

Telegram bot for VPN subscriptions.

## Structure
- `app/` — future application modules (config, clients, services, handlers)
- `data/` — database utilities and assets
- `handlers/` — current bot handlers
- `payments/` — payment integration and webhook
- `utils/` — legacy utilities (VPN integration, reminders)

## Setup
1. Create `.env` from `.env.example` in the repository root.
2. Set `USER_BOT_TOKEN` in `.env`.
3. Install requirements from `requirements.txt` in the repository root.
4. Run `bot.py` for polling or `run_webhook.py` for webhook mode.

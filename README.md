# KairaVPN Telegram Bots

This repository contains two related Telegram bots:

- `admin_bot/` — admin bot to manage the Remnawave panel and users
- `user_bot/` — user-facing bot for subscriptions and payments

## Read More

- Admin bot documentation: `admin_bot/README.md`
- User bot documentation: `user_bot/README.md`

## Quick Start

1) Create `.env` from `.env.example` in the repository root.
2) Install dependencies:
   - `pip install -r requirements.txt`
3) Run the bot you need:
   - Admin bot: `python admin_bot/main.py`
   - User bot (polling): `python user_bot/bot.py`
   - User bot (webhook): `python user_bot/run_webhook.py`

## Notes

- Tokens are configured in the root `.env` file:
  - `Admin_bot_token` for admin bot
  - `USER_BOT_TOKEN` for user bot
- See each bot's README for detailed setup and features.

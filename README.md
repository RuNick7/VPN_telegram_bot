# VPN Telegram Bots

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

## How to run web mvp locally

1) Backend:
   - `cd web/backend`
   - `python3.12 -m venv .venv312`
   - `source .venv312/bin/activate`
   - `pip install -r requirements.txt`
   - `cp .env.example .env`
   - fill required env values in `.env`:
     - `TELEGRAM_BOT_TOKEN`
     - `YOOKASSA_SHOP_ID`
     - `YOOKASSA_SECRET_KEY`
     - `REMNAWAVE_BASE_URL`
   - `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`

2) Frontend:
   - open a new terminal
   - `cd web/frontend`
   - `python -m http.server 5173`

3) Open:
   - `http://127.0.0.1:5173`
   - login by magic link or Telegram widget
   - cabinet: `http://127.0.0.1:5173/cabinet/`

## Web MVP smoke flow

1) `POST /api/auth/telegram` (or magic link login)
2) `GET /api/subscription`
3) `POST /api/subscription/extend` -> get `confirmation_url` + `payment_id`
4) `GET /api/payments/{payment_id}` -> usually `pending` before real payment
5) `POST /api/payments/webhook/yookassa`:
   - ignored event example: `payment.waiting_for_capture`
   - success event: `payment.succeeded`
6) `GET /api/payments/{payment_id}` again
   - after real payment + webhook should become `succeeded`

## Troubleshooting (web)

- CORS error in browser:
  - frontend must run from `http://127.0.0.1:5173` or `http://localhost:5173`
  - restart backend after CORS/env changes
- 401 Unauthorized:
  - missing/expired auth cookie
  - login again and recheck `/api/me`
- 502 from subscription/payment endpoints:
  - check required env values in `web/backend/.env`
  - check network access to Remnawave panel domain
- payment remains `pending`:
  - payment is not completed in YooKassa yet, or real webhook `payment.succeeded` not delivered
  - verify `payment_id` and webhook settings (secret/cidrs if enabled)

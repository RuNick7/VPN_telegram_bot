# KairaVPN — деплой на Ubuntu 24.04

Этот каталог содержит готовые юниты systemd и конфиг nginx для production-стенда.

Структура:

```
deploy/
├── README.md                     # этот файл
├── systemd/
│   ├── kaira-user-bot.service    # polling user-bot (aiogram)
│   ├── kaira-webhook.service     # YooKassa webhook (aiohttp) — отдельный домен
│   ├── kaira-admin-bot.service   # admin-bot (aiogram)
│   ├── kaira-web-api.service     # FastAPI веб-кабинета (uvicorn) на 127.0.0.1:8001
│   └── kaira-web.service         # Next.js фронтенд (next start) на 127.0.0.1:3000
└── nginx/
    ├── kaira-webhook.conf        # reverse-proxy 443 -> 127.0.0.1:8000 для webhook ЮKassa
    └── kaira-app.conf            # reverse-proxy 443 -> 127.0.0.1:3000 (Next.js)
                                  #                  + 127.0.0.1:8001 (/api/* -> FastAPI)
```

Юниты рассчитаны на:

- путь установки `/opt/kaira/KairaVPN_admin_bot`
- venv по адресу `/opt/kaira/KairaVPN_admin_bot/.venv`
- общий `.env` в корне репо
- системного пользователя `kaira`

Если у вас другие пути/пользователь — поменяйте `User=`, `WorkingDirectory=`,
`EnvironmentFile=` и `ExecStart=` в каждом `*.service`.

---

## 1. Что было исправлено в коде

Главная проблема ваших падений: **синхронные сетевые вызовы** (YooKassa SDK,
Remnawave SDK через `requests`) внутри **асинхронных** обработчиков
aiogram/aiohttp. Когда upstream отвечал медленно или соединение «провисало»,
event loop замирал в `socket.recv()` под GIL — и:

- бот переставал отвечать (event loop заморожен);
- `systemctl stop`/`restart` тянулся ~30 секунд, пока systemd не убивал процесс
  по `SIGKILL`, потому что Python не мог обработать `SIGTERM` из-за висящего
  syscall.

Что поправили:

- `user_bot/payments/webhook.py` — `fetch_payment`,
  `extend_subscription_by_telegram_id` и все обращения к SQLite вынесены в
  `asyncio.to_thread(...)` + `asyncio.wait_for(..., timeout=N)`.
- `user_bot/handlers/payments.py` — `create_payment` (YooKassa) обёрнут в
  thread + таймаут 15 сек. Добавлены человеко-понятные ошибки таймаута.
- `user_bot/handlers/menu.py`, `user_bot/handlers/setup.py`,
  `user_bot/handlers/referrals.py`, `user_bot/middlewares/email_gate.py` —
  все sync remnawave/SQLite вызовы переведены на `asyncio.to_thread`.
- `user_bot/app/clients/remnawave/client.py` — у всех `requests.*` теперь
  раздельный `(connect, read)` таймаут.
- `user_bot/run_webhook.py` — добавлен `shutdown_timeout=5`, поддержка env
  `WEBHOOK_HOST/WEBHOOK_PORT`, healthcheck `/healthz`. По умолчанию слушает
  только `127.0.0.1`.

После этих правок зависший upstream больше не блокирует обработку других
сообщений и не мешает graceful shutdown.

---

## 2. Подготовка сервера (Ubuntu 24.04)

Один раз:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git nginx ufw

# системный пользователь без shell для бота
sudo useradd --system --create-home --home-dir /home/kaira \
    --shell /usr/sbin/nologin kaira

# каталог проекта
sudo mkdir -p /opt/kaira
sudo chown kaira:kaira /opt/kaira
```

## 3. Раскатка кода

```bash
sudo -u kaira -H bash <<'EOF'
cd /opt/kaira
git clone https://github.com/your-org/KairaVPN_admin_bot.git
cd KairaVPN_admin_bot
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
EOF
```

`.env` в корне (`/opt/kaira/KairaVPN_admin_bot/.env`) — скопировать из
`.env.example` и заполнить. Права 600:

```bash
sudo cp /opt/kaira/KairaVPN_admin_bot/.env.example \
        /opt/kaira/KairaVPN_admin_bot/.env
sudo chown kaira:kaira /opt/kaira/KairaVPN_admin_bot/.env
sudo chmod 600          /opt/kaira/KairaVPN_admin_bot/.env
sudoedit                 /opt/kaira/KairaVPN_admin_bot/.env
```

## 4. systemd-юниты

```bash
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/systemd/kaira-user-bot.service   /etc/systemd/system/
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/systemd/kaira-webhook.service    /etc/systemd/system/
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/systemd/kaira-admin-bot.service  /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now kaira-user-bot.service
sudo systemctl enable --now kaira-webhook.service
sudo systemctl enable --now kaira-admin-bot.service
```

Проверить:

```bash
systemctl status kaira-user-bot kaira-webhook kaira-admin-bot
journalctl -u kaira-webhook -f          # live-логи webhook'а
journalctl -u kaira-user-bot -n 200     # последние 200 строк
```

Ключевые опции в юнитах (зачем они нужны):

| опция | значение | для чего |
|------|----------|----------|
| `Restart=always` | `always` | если процесс упал/был убит — поднимется снова |
| `RestartSec=3` | 3 сек | пауза между рестартами |
| `KillSignal=SIGINT` | `SIGINT` | aiogram/aiohttp обрабатывают как graceful shutdown |
| `TimeoutStopSec=10` | 10 сек | если за 10 сек не вышел — `SIGKILL`. Это вместо ваших ~30 сек ожидания |
| `SendSIGKILL=yes` | да | гарантированно добиваем зависший процесс |
| `StartLimitBurst=10` | 10/5 мин | защита от crash-loop |
| `LimitNOFILE=65535` | 65535 | лимит на открытые сокеты |
| `ProtectSystem=full` + `PrivateTmp=true` | sandbox | защита от случайной записи в `/usr`, `/etc` и пр. |

## 5. Закрываем webhook от внешнего мира + nginx

Сейчас в логах видны мусорные сканеры (`POST /api/route`, `GET /robots.txt`,
`UNKNOWN /`). Это потому, что aiohttp слушал `0.0.0.0:8000`. После наших правок
он по умолчанию слушает `127.0.0.1:8000`, а наружу выставляется через nginx.

```bash
# 1) разрешаем 80/443 и SSH, закрываем 8000
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw deny 8000/tcp
sudo ufw enable

# 2) кладём конфиг nginx
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/nginx/kaira-webhook.conf \
        /etc/nginx/sites-available/kaira-webhook.conf
sudo ln -sf /etc/nginx/sites-available/kaira-webhook.conf \
            /etc/nginx/sites-enabled/kaira-webhook.conf

# 3) подставьте свой домен внутри файла (server_name webhook.example.com)
sudoedit /etc/nginx/sites-available/kaira-webhook.conf

# 4) сертификат
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d webhook.example.com

# 5) тест и reload
sudo nginx -t
sudo systemctl reload nginx
```

В YooKassa в кабинете укажите URL вебхука:
`https://webhook.example.com/webhook-yookassa`.

Конфиг **отбрасывает 444** (rst соединения) всё, что не `POST /webhook-yookassa`
с разрешённых IP YooKassa, а также любые методы кроме POST. Сканеры перестанут
шуршать в логах.

## 6. Эксплуатация

### Перезапуск

```bash
sudo systemctl restart kaira-webhook
sudo systemctl restart kaira-user-bot
sudo systemctl restart kaira-admin-bot
```

С новыми юнитами рестарт занимает ~3-4 секунды (а не 30+).

### Если бот залип

```bash
# хард-стоп (форс-килл за 10 сек):
sudo systemctl kill --signal=SIGKILL kaira-user-bot
sudo systemctl start kaira-user-bot

# смотрим, что было перед смертью:
journalctl -u kaira-user-bot -n 300 --no-pager
```

### Мониторинг

Минимум что стоит поставить — алерт на отсутствие логов в журнале > 10 минут.
Плюс `failed`-состояние юнита через `systemctl is-failed`.

Пример однострочника для cron:

```bash
*/5 * * * * /usr/bin/systemctl is-active --quiet kaira-webhook || \
    /usr/bin/systemctl restart kaira-webhook
```

(хотя `Restart=always` обычно достаточно).

### Обновление кода

```bash
sudo -u kaira -H bash <<'EOF'
cd /opt/kaira/KairaVPN_admin_bot
git pull
.venv/bin/pip install -r requirements.txt
EOF

sudo systemctl restart kaira-user-bot kaira-webhook kaira-admin-bot
```

---

## 7. Веб-кабинет (`app.kairavpn.pro`)

Веб-кабинет — это **один домен** `app.kairavpn.pro`, который nginx
разводит между двумя процессами:

- `kaira-web-api.service` — FastAPI на `127.0.0.1:8001` (бэкенд кабинета).
- `kaira-web.service` — Next.js на `127.0.0.1:3000` (фронтенд + PWA).

Webhook ЮKassa **остаётся на отдельном домене** `webhook.kaira.yet.moe`
(сервис `kaira-webhook.service`). В YooKassa **ничего не меняем**.

### 7.1. DNS

```
app.kairavpn.pro    A    <IP сервера>
app.kairavpn.pro    AAAA <IPv6, если есть>
```

### 7.2. Зависимости

Backend использует общий `.venv` репозитория. Установить дополнительные
питон-зависимости (FastAPI, pywebpush и т.п.):

```bash
sudo -u kaira -H /opt/kaira/KairaVPN_admin_bot/.venv/bin/pip install \
  -r /opt/kaira/KairaVPN_admin_bot/requirements.txt
```

Node.js 20 LTS для фронта:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

Сборка фронта:

```bash
sudo -u kaira -H bash <<'EOF'
cd /opt/kaira/KairaVPN_admin_bot/web/frontend
npm ci
npm run build
EOF
```

При каждом обновлении:

```bash
sudo -u kaira -H bash <<'EOF'
cd /opt/kaira/KairaVPN_admin_bot
git pull
.venv/bin/pip install -r requirements.txt
cd web/frontend
npm ci
npm run build
EOF

sudo systemctl restart kaira-web-api kaira-web
```

### 7.3. ENV

Все переменные кладём в общий `/opt/kaira/KairaVPN_admin_bot/.env`
(бэкенд читает и его, и `web/backend/.env`). Из нового, что нужно
заполнить под кабинет:

```bash
JWT_SECRET=<openssl rand -base64 48>
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax

APP_BASE_URL=https://app.kairavpn.pro
API_BASE_URL=https://app.kairavpn.pro
WEB_PAYMENT_RETURN_URL=https://app.kairavpn.pro/cabinet/payment-callback
CORS_ORIGINS=https://app.kairavpn.pro

EMAIL_SENDER_MODE=smtp
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USERNAME=no-reply@kairavpn.pro
SMTP_PASSWORD=<app-password>
SMTP_FROM_EMAIL=no-reply@kairavpn.pro
SMTP_USE_SSL=true
SMTP_USE_TLS=false

TELEGRAM_BOT_USERNAME=KairaVPN_Bot

# секрет, по которому user_bot ходит в /api/internal/* (loopback)
WEB_INTERNAL_SECRET=<openssl rand -hex 32>

# VAPID для web-push: один раз — `npx web-push generate-vapid-keys --json`
VAPID_PUBLIC_KEY=<publicKey>
VAPID_PRIVATE_KEY=<privateKey>
VAPID_CONTACT_EMAIL=mailto:nitratex@kairavpn.pro
```

Для фронта в `web/frontend/.env`:

```bash
NEXT_PUBLIC_SITE_URL=https://app.kairavpn.pro
NEXT_PUBLIC_FAQ_URL=https://nitratex-company.gitbook.io/kairavpn/
API_BASE_URL=http://127.0.0.1:8001
```

### 7.4. PWA-иконки

Фронт ожидает в `web/frontend/public/icons/` четыре файла:
`icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `badge-72.png`,
плюс `web/frontend/public/apple-touch-icon.png` и `favicon.ico`.

Команды нарезки из одного исходника описаны в
`web/frontend/public/icons/README.md`. Без иконок PWA технически
работает, но Lighthouse PWA audit будет ругаться, а на Android
вместо логотипа покажется белый квадратик.

### 7.5. systemd-юниты

```bash
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/systemd/kaira-web-api.service /etc/systemd/system/
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/systemd/kaira-web.service     /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now kaira-web-api.service
sudo systemctl enable --now kaira-web.service
```

Проверить:

```bash
systemctl status kaira-web-api kaira-web
journalctl -u kaira-web-api -n 200 --no-pager
journalctl -u kaira-web -n 200 --no-pager
curl -fsS http://127.0.0.1:8001/api/me     # 401 — норма без сессии
curl -fsS http://127.0.0.1:3000/ | head -c 300
```

### 7.6. nginx и TLS

```bash
sudo cp /opt/kaira/KairaVPN_admin_bot/deploy/nginx/kaira-app.conf \
        /etc/nginx/sites-available/kaira-app
sudo ln -sf /etc/nginx/sites-available/kaira-app /etc/nginx/sites-enabled/kaira-app

# Сертификат Let's Encrypt — один на единый домен:
sudo certbot --nginx -d app.kairavpn.pro

sudo nginx -t
sudo systemctl reload nginx
```

В YooKassa **ничего не меняем** — webhook продолжает приходить на
`https://webhook.kaira.yet.moe/webhook-yookassa`, который обрабатывает
старый `kaira-webhook.service`.

### 7.7. Перезапуск user_bot

`user_bot` теперь умеет обрабатывать `/start web_<token>` и слать
push'ы при успешных платежах. Перечитайте `.env` и перезапустите:

```bash
sudo systemctl restart kaira-user-bot
```

### 7.8. Проверка из интернета

```bash
curl -fsSI https://app.kairavpn.pro/ | head -n 5
curl -i    https://app.kairavpn.pro/api/me                    # 401 — норма
curl -fsS  https://app.kairavpn.pro/manifest.webmanifest | head -c 200

# Telegram deep-link: должен вернуть { token, deeplink, expires_at }
curl -s -X POST https://app.kairavpn.pro/api/auth/telegram/start | jq

# Internal endpoint снаружи должен закрываться 444:
curl -i https://app.kairavpn.pro/api/internal/telegram-link/confirm
```

### 7.9. PWA + push

После деплоя запросите у браузера установку (Chrome/Edge на Android
покажут баннер автоматически; iOS — Safari → «Поделиться» → «На экран
„Домой"»). Чтобы push'и заработали:

1. Пользователь должен быть авторизован в кабинете.
2. Открыть `/cabinet`, в карточке «Уведомления» нажать «Включить
   уведомления», подтвердить разрешение.
3. На iOS push работает только если приложение **установлено на
   главный экран** (iOS 16.4+). В обычной вкладке Safari push iOS не
   доставит.

Тестовый push (от имени самого web-api):

```bash
curl -i -X POST http://127.0.0.1:8001/api/internal/push/send \
  -H 'Content-Type: application/json' \
  -H "X-Kaira-Internal-Secret: $WEB_INTERNAL_SECRET" \
  -d '{"telegram_id": <ВАШ_TG_ID>, "title": "Тест", "body": "Push работает"}'
```

## 8. Быстрая проверка после деплоя

```bash
# webhook жив локально?
curl -fsS http://127.0.0.1:8000/healthz
# {"status":"ok"}

# и из интернета через nginx?
curl -fsS https://webhook.example.com/healthz

# user-bot отвечает на /start в Telegram? -> руками

# логи без ошибок?
journalctl -u kaira-webhook -n 100 --no-pager | grep -iE 'error|timeout'
journalctl -u kaira-user-bot -n 100 --no-pager | grep -iE 'error|timeout'
```

Если всё ОК — оставляем работать. Падений из-за зависшего YooKassa/Remnawave
больше быть не должно: внутри обработчика стоят таймауты 15-20 секунд,
а сами вызовы крутятся в thread-pool, не блокируя event loop.

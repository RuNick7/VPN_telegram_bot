import logging
import os

from aiohttp import web

from payments.webhook import yookassa_webhook_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

logger.info("Инициализация приложения для обработки webhook'ов от Yookassa.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "127.0.0.1")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8000"))
# Сколько секунд ждём корректного завершения in-flight запросов при остановке.
WEBHOOK_SHUTDOWN_TIMEOUT = float(os.getenv("WEBHOOK_SHUTDOWN_TIMEOUT", "5"))

app = web.Application()


@web.middleware
async def log_webhook_request(request: web.Request, handler):
    logger.info(
        "YooKassa webhook hit: method=%s path=%s remote=%s",
        request.method,
        request.path,
        request.remote,
    )
    return await handler(request)


@web.middleware
async def health_check_first(request: web.Request, handler):
    if request.method == "GET" and request.path in ("/health", "/healthz"):
        return web.json_response({"status": "ok"})
    return await handler(request)


app.middlewares.append(health_check_first)
app.middlewares.append(log_webhook_request)
app.router.add_post("/webhook-yookassa", yookassa_webhook_handler)


if __name__ == "__main__":
    # shutdown_timeout — после SIGINT/SIGTERM aiohttp ждёт N секунд завершения
    # текущих запросов и затем закрывает loop. Без этого systemd может ждать
    # до TimeoutStopSec (обычно 90s) и слать SIGKILL.
    web.run_app(
        app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        shutdown_timeout=WEBHOOK_SHUTDOWN_TIMEOUT,
        access_log=None,
    )

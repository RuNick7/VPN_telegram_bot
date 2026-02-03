import logging
from aiohttp import web
from payments.webhook import yookassa_webhook_handler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logger.info("Инициализация приложения для обработки webhook'ов от Yookassa.")
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


app.middlewares.append(log_webhook_request)
# Основной URL для HTTP-уведомлений YooKassa
app.router.add_post("/Webhook-ChatGPT", yookassa_webhook_handler)

if __name__ == "__main__":
    # Запускаем сервер на порту 8000
    web.run_app(app, port=8000)

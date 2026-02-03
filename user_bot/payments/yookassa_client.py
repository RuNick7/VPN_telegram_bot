import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from yookassa import Configuration, Payment

# Загружаем переменные окружения
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Подключение к YooKassa
SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

if not SHOP_ID or not SECRET_KEY:
    raise ValueError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY must be set in the .env file.")

Configuration.account_id = SHOP_ID
Configuration.secret_key = SECRET_KEY


def create_payment(amount, description, return_url, telegram_id, days_to_extend, is_gift=False):
    logger.info(f"[PAYMENT] Создание платежа: amount={amount} description='{description}' "
                f"telegram_id={telegram_id} is_gift={is_gift} days_to_extend={days_to_extend}")

    try:
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "telegram_id": telegram_id,
                "days_to_extend": days_to_extend,
                "is_gift": "true" if is_gift else "false"
            },
            "receipt": {
                "customer": {
                    "email": "no-reply@nitravpn.com"  # Можно указать email пользователя, если есть
                },
                "items": [
                    {
                        "description": description,
                        "quantity": "1.00",
                        "amount": {
                            "value": str(amount),
                            "currency": "RUB"
                        },
                        "vat_code": 1,  # 1 — без НДС (для самозанятых)
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        })

        logger.info(f"[PAYMENT] Платёж успешно создан. ID: {payment.id}")
        return payment

    except Exception as e:
        logger.error(f"[PAYMENT] Ошибка создания платежа: {e}")
        raise


def fetch_payment(payment_id: str):
    """Fetch payment status/details from YooKassa API."""
    try:
        payment = Payment.find_one(payment_id)
        logger.info("[PAYMENT] Платёж получен из YooKassa: id=%s status=%s", payment_id, payment.status)
        return payment
    except Exception as e:
        logger.error("[PAYMENT] Ошибка получения платежа %s из YooKassa: %s", payment_id, e)
        raise


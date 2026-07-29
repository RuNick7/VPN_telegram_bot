import logging

from tgvpn_shared.settings import get_settings
from yookassa import Configuration, Payment

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

_settings = get_settings()
_settings.require("yookassa_shop_id", "yookassa_secret_key")

Configuration.account_id = _settings.yookassa_shop_id
Configuration.secret_key = _settings.yookassa_secret_key


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


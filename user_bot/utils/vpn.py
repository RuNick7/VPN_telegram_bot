import time

from app.services.remnawave import vpn_service


def get_token(telegram_id: int) -> str:
    return vpn_service.get_token(telegram_id)


def get_user_expire(username: str, token: str | None = None) -> int:
    return vpn_service.get_user_expire(username, token)


def ensure_vpn_profile_created_if_missing(telegram_id: int) -> None:
    return vpn_service.ensure_vpn_profile_created_if_missing(telegram_id)


def extend_subscription_by_telegram_id(telegram_id: int, days_to_add: int) -> str:
    return vpn_service.extend_subscription_by_telegram_id(telegram_id, days_to_add)


def create_vpn_user_by_telegram_id(telegram_id: int, days_to_add: int) -> bool:
    return vpn_service.create_vpn_user_by_telegram_id(telegram_id, days_to_add)


def get_subscription_url(username: str, token: str | None = None) -> str:
    return vpn_service.get_subscription_url(username, token)


def calculate_new_expire(current_expire: int, days_to_add: int) -> int:
    now = int(time.time())
    days_to_add = int(days_to_add)
    return max(current_expire, now) + days_to_add * 86400

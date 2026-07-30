import re
import time

from handlers.constants import PRICES, SECONDS_IN_DAY


def escape_markdown_v2(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    escape_chars = r"*_[]()~`>#+-=|{}.!<>"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def days_to_unixtime(days: int) -> int:
    """Смещение от текущего момента на N дней."""
    return int(time.time()) + days * SECONDS_IN_DAY


def unixtime_to_days(ts: int) -> int:
    """Сколько дней осталось до ts от «сейчас» (>=0)."""
    return max(0, (ts - int(time.time())) // SECONDS_IN_DAY)


def get_subscription_price(months: int, referred_people: int) -> int:
    if months not in (1, 3, 6, 12):
        raise ValueError("Недопустимый срок подписки")
    tier = min(referred_people, 5)
    return PRICES[tier][months]


def traffic_pack_discount(gigabytes: int, price: int, packs: dict[int, int]) -> int:
    """
    How much cheaper per gigabyte this pack is than the smallest one, in percent.

    The smallest pack sets the reference rate, so it is always 0% and larger
    packs show what buying in bulk saves:

        discount = (1 - price / (gigabytes / base_gb * base_price)) * 100

    Rounded down, so the advertised saving is never larger than the real one.
    """
    if not packs:
        return 0
    base_gb = min(packs)
    base_price = packs[base_gb]
    if base_gb <= 0 or base_price <= 0 or gigabytes <= 0:
        return 0

    price_at_base_rate = gigabytes / base_gb * base_price
    if price_at_base_rate <= 0:
        return 0
    # Negative would mean a pack priced *worse* than the baseline; clamp to 0
    # rather than advertising "-0%" or a markup as if it were a saving.
    return max(0, int((1 - price / price_at_base_rate) * 100))


def traffic_pack_label(gigabytes: int, price: int, packs: dict[int, int]) -> str:
    """Button caption: `10 ГБ — 119₽ (-33%)`, with no suffix at 0%."""
    discount = traffic_pack_discount(gigabytes, price, packs)
    suffix = f" (-{discount}%)" if discount else ""
    return f"{gigabytes} ГБ — {price}₽{suffix}"

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


def _bulk_discount(units: int, price: int, base_units: int, base_price: int) -> int:
    """
    Percent saved versus buying `units` at the smallest option's unit rate.

        (1 - price / (units / base_units * base_price)) * 100

    Rounded down, so an advertised saving is never larger than the real one,
    and floored at 0 so something priced *worse* than the baseline is never
    dressed up as a discount.
    """
    if base_units <= 0 or base_price <= 0 or units <= 0:
        return 0
    price_at_base_rate = units / base_units * base_price
    if price_at_base_rate <= 0:
        return 0
    return max(0, int((1 - price / price_at_base_rate) * 100))


def subscription_discount(months: int, price: int, referred_people: int) -> int:
    """
    Percent saved on a multi-month plan versus paying monthly.

    Measured at the user's own referral tier, so it shows the bulk saving
    only. Mixing in the referral discount would double-count: the monthly
    price they are compared against is already discounted by the same tier.
    """
    if months <= 1:
        return 0
    monthly = get_subscription_price(1, referred_people)
    return _bulk_discount(months, price, 1, monthly)


def subscription_label(duration: str, months: int, price: int, referred_people: int) -> str:
    """Button caption: `3 месяца — 249₽ (-6%)`, with no suffix at 0%."""
    discount = subscription_discount(months, price, referred_people)
    suffix = f" (-{discount}%)" if discount else ""
    return f"{duration} — {price}₽{suffix}"


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
    return _bulk_discount(gigabytes, price, base_gb, packs[base_gb])


def traffic_pack_label(gigabytes: int, price: int, packs: dict[int, int]) -> str:
    """Button caption: `10 ГБ — 119₽ (-33%)`, with no suffix at 0%."""
    discount = traffic_pack_discount(gigabytes, price, packs)
    suffix = f" (-{discount}%)" if discount else ""
    return f"{gigabytes} ГБ — {price}₽{suffix}"

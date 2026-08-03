TARIFFS = {
    1: {"amount": 89.0, "days": 30},
    3: {"amount": 249.0, "days": 90},
    6: {"amount": 479.0, "days": 180},
    12: {"amount": 899.0, "days": 360},
}

PRICES = {
    0: {1: 89, 3: 249, 6: 479, 12: 899},
    1: {1: 69, 3: 200, 6: 380, 12: 730},
    2: {1: 49, 3: 140, 6: 270, 12: 520},
    3: {1: 29, 3: 80,  6: 140, 12: 250},
    4: {1: 15, 3: 40,  6: 60,  12: 100},
    5: {1: 9,  3: 25,  6: 40,  12: 59},
}

SECONDS_IN_DAY = 86_400


def trial_days() -> int:
    """
    The free period a new bot account gets, from TRIAL_DAYS.

    A function rather than a constant because this used to be a hardcoded 30
    that ignored the setting entirely: the site handed out what .env said and
    the bot handed out 30, from the same deployment. Reading it at call time
    also keeps the value out of import order, which matters for the tests.
    """
    from tgvpn_shared.settings import get_settings

    return max(0, get_settings().trial_days)


def trial_link_bonus_days() -> int:
    """What connecting the second identity is worth. See TRIAL_LINK_BONUS_DAYS."""
    from tgvpn_shared.settings import get_settings

    return max(0, get_settings().trial_link_bonus_days)

# Paid LTE traffic packs, in gigabytes -> rubles.
#
# Flat pricing on purpose: unlike subscriptions (see PRICES above, where the
# referral count picks a discount tier), traffic costs the same for everyone.
# It is a consumable resold at cost, not a plan someone can earn their way
# down -- and stacking the referral ladder on top of it would let a
# five-referral user buy traffic for a fraction of what it costs to serve.
LTE_TRAFFIC_PACKS = {
    5: 89,
    10: 119,
    15: 149,
    30: 239,
}

# -*- coding: utf-8 -*-


class CardType:
    """
    Тип банковской карты. 
    """  # noqa: E501

    """
    Список допустимых значений
    """
    MASTER_CARD = 'MasterCard'
    """MasterCard` (для карт Mastercard и Maestro)."""
    VISA = 'Visa'
    """Visa` (для карт Visa и Visa Electron)."""
    MIR = 'MIR'
    """Mir."""
    UNION_PAY = 'UnionPay'
    """UnionPay."""
    CUP = 'CUP'
    """CUP."""
    JCB = 'JCB'
    """JCB."""
    AMERICAN_EXPRESS = 'AmericanExpress'
    """AmericanExpress."""
    DINERS_CLUB = 'DinersClub'
    """DinersClub."""
    UNKNOWN = 'Unknown'
    """Unknown."""


class CardSource:
    """
    Источник данных банковской карты.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    APPLE_PAY = 'apple_pay'
    """Источник данных ApplePay."""
    GOOGLE_PAY = 'GooglePay'
    """Источник данных ApplePay."""
    MIR_PAY = 'mir_pay'
    """Источник данных MirPay."""

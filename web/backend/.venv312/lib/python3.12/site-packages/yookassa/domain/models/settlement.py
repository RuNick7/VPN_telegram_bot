# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount


class Settlement(BaseObject):
    """
    Информация о совершенных расчетах. 
    """  # noqa: E501

    __type = None
    """Тип расчета."""  # noqa: E501

    __amount = None
    """Сумма расчета."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели Settlement.

        :return: type модели Settlement.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели Settlement.

        :param value: type модели Settlement.
        :type value: str
        """
        self.__type = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели Settlement.

        :return: amount модели Settlement.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели Settlement.

        :param value: amount модели Settlement.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')


class SettlementType(object):
    """
    Тип расчета.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    CASHLESS = 'cashless'
    """Безналичный расчет."""
    PREPAYMENT = 'prepayment'
    """Предоплата (аванс)."""
    POSTPAYMENT = 'postpayment'
    """Постоплата (кредит)."""
    CONSIDERATION = 'consideration'
    """Встречное предоставление."""


class SettlementPayoutType(object):
    """
    Тип операции. Фиксированное значение: `payout` — выплата продавцу. 
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PAYOUT = 'payout'
    """Выплата продавцу"""

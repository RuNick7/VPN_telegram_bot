# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount


class RefundSource(BaseObject):
    """
    Данные о том, с какого магазина и какую сумму нужно удержать для проведения возврата. Сейчас в этом параметре можно передать данные только одного магазина.
    """  # noqa: E501

    __account_id = None
    """Идентификатор магазина, для которого вы хотите провести возврат."""  # noqa: E501

    __amount = None
    """Сумма возврата."""  # noqa: E501

    __platform_fee_amount = None
    """Комиссия, которую вы удержали при оплате, и хотите вернуть."""  # noqa: E501

    @property
    def account_id(self):
        """
        Возвращает account_id модели RefundSource.

        :return: account_id модели RefundSource.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """
        Устанавливает account_id модели RefundSource.

        :param value: account_id модели RefundSource.
        :type value: str
        """
        self.__account_id = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели RefundSource.

        :return: amount модели RefundSource.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели RefundSource.

        :param value: amount модели RefundSource.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def platform_fee_amount(self):
        """
        Возвращает platform_fee_amount модели RefundSource.

        :return: platform_fee_amount модели RefundSource.
        :rtype: Amount
        """
        return self.__platform_fee_amount

    @platform_fee_amount.setter
    def platform_fee_amount(self, value):
        """
        Устанавливает platform_fee_amount модели RefundSource.

        :param value: platform_fee_amount модели RefundSource.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__platform_fee_amount = Amount(value)
        elif isinstance(value, Amount):
            self.__platform_fee_amount = value
        else:
            raise TypeError('Invalid platform_fee_amount value type')

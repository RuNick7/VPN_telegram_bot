# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PaymentMethodHolder(BaseObject):
    """Данные магазина, для которого сохраняется способ оплаты."""  # noqa: E501

    __account_id = None
    """Идентификатор магазина в ЮKassa."""  # noqa: E501

    __gateway_id = None
    """Идентификатор субаккаунта. Используется для разделения потоков платежей в рамках одного аккаунта."""  # noqa: E501

    @property
    def account_id(self):
        """Возвращает account_id модели SavePaymentMethodHolder.

        :return: account_id модели SavePaymentMethodHolder.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """Устанавливает account_id модели SavePaymentMethodHolder.

        :param value: account_id модели SavePaymentMethodHolder.
        :type value: str
        """
        self.__account_id = value

    @property
    def gateway_id(self):
        """Возвращает gateway_id модели SavePaymentMethodHolder.

        :return: gateway_id модели SavePaymentMethodHolder.
        :rtype: str
        """
        return self.__gateway_id

    @gateway_id.setter
    def gateway_id(self, value):
        """Устанавливает gateway_id модели SavePaymentMethodHolder.

        :param value: gateway_id модели SavePaymentMethodHolder.
        :type value: str
        """
        self.__gateway_id = value

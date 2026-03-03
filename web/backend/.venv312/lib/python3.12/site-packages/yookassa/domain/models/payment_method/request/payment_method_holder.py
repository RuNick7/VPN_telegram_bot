# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PaymentMethodHolder(BaseObject):
    """Данные магазина, для которого сохраняется способ оплаты."""  # noqa: E501

    __gateway_id = None
    """Идентификатор субаккаунта. Используется для разделения потоков платежей в рамках одного аккаунта."""  # noqa: E501

    @property
    def gateway_id(self):
        """Возвращает gateway_id модели PaymentMethodHolder.

        :return: gateway_id модели PaymentMethodHolder.
        :rtype: str
        """
        return self.__gateway_id

    @gateway_id.setter
    def gateway_id(self, value):
        """Устанавливает gateway_id модели PaymentMethodHolder.

        :param value: gateway_id модели PaymentMethodHolder.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__gateway_id = cast_value
        else:
            raise ValueError('Invalid gateway_id value')

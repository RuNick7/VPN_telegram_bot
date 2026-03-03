# -*- coding: utf-8 -*-
import re

from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataMobileBalance(PaymentData):
    """
    Данные для оплаты с баланса мобильного телефона.
    """  # noqa: E501

    __phone = None
    """Телефон, с баланса которого осуществляется платеж. Указывается в формате [ITU-T E.164](https://ru.wikipedia.org/wiki/E.164), например ~`79000000000`. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataMobileBalance, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.MOBILE_BALANCE:
            self.type = PaymentMethodType.MOBILE_BALANCE

    @property
    def phone(self):
        """
        Возвращает phone модели PaymentDataMobileBalance.

        :return: phone модели PaymentDataMobileBalance.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели PaymentDataMobileBalance.

        :param value: phone модели PaymentDataMobileBalance.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{4,15}$', cast_value):
            self.__phone = cast_value
        else:
            raise ValueError('Invalid phone value type')

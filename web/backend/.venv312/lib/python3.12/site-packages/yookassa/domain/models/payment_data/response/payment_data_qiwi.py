# -*- coding: utf-8 -*-
import re

from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData


class PaymentDataQiwi(ResponsePaymentData):
    """
    Оплата из кошелька QIWI Wallet.
    """  # noqa: E501

    __phone = None
    """Телефон, на который зарегистрирован аккаунт в QIWI. Указывается в формате [ITU-T E.164](https://ru.wikipedia.org/wiki/E.164), например ~`79000000000`. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataQiwi, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.QIWI:
            self.type = PaymentMethodType.QIWI

    @property
    def phone(self):
        """
        Возвращает phone модели PaymentDataQiwi.

        :return: phone модели PaymentDataQiwi.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели PaymentDataQiwi.

        :param value: phone модели PaymentDataQiwi.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{4,15}$', cast_value):
            self.__phone = cast_value
        else:
            raise ValueError('Invalid phone value type')

# -*- coding: utf-8 -*-
import re

from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.response.payment_data_bank_card import PaymentDataBankCard


class PaymentDataSberbank(PaymentDataBankCard):
    """
    Оплата через SberPay.
    """  # noqa: E501

    __phone = None
    """Телефон пользователя, на который зарегистрирован аккаунт в SberPay. Указывается в формате [ITU-T E.164](https://ru.wikipedia.org/wiki/E.164), например ~`79000000000`. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataSberbank, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBERBANK:
            self.type = PaymentMethodType.SBERBANK

    @property
    def phone(self):
        """
        Возвращает phone модели PaymentDataSberbank.

        :return: phone модели PaymentDataSberbank.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели PaymentDataSberbank.

        :param value: phone модели PaymentDataSberbank.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{4,15}$', cast_value):
            self.__phone = cast_value
        else:
            raise ValueError('Invalid phone value type')

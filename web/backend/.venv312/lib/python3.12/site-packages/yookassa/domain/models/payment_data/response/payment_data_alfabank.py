# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData


class PaymentDataAlfabank(ResponsePaymentData):
    """
    Оплата через Альфа-Клик.
    """  # noqa: E501

    __login = None
    """Логин пользователя в Альфа-Клике (привязанный телефон или дополнительный логин)."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataAlfabank, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.ALFABANK:
            self.type = PaymentMethodType.ALFABANK

    @property
    def login(self):
        """
        Возвращает login модели PaymentDataAlfabank.

        :return: login модели PaymentDataAlfabank.
        :rtype: str
        """
        return self.__login

    @login.setter
    def login(self, value):
        """
        Устанавливает login модели PaymentDataAlfabank.

        :param value: login модели PaymentDataAlfabank.
        :type value: str
        """
        self.__login = str(value)

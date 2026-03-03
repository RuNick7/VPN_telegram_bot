# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataApplepay(PaymentData):
    """
    Платежные данные для проведения оплаты при помощи Apple Pay.
    """  # noqa: E501

    __payment_data = None
    """Содержимое поля paymentData объекта PKPaymentToken, закодированное в Base64."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataApplepay, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.APPLEPAY:
            self.type = PaymentMethodType.APPLEPAY

    @property
    def payment_data(self):
        """
        Возвращает payment_data модели PaymentDataApplepay.

        :return: payment_data модели PaymentDataApplepay.
        :rtype: str
        """
        return self.__payment_data

    @payment_data.setter
    def payment_data(self, value):
        """
        Устанавливает payment_data модели PaymentDataApplepay.

        :param value: payment_data модели PaymentDataApplepay.
        :type value: str
        """
        self.__payment_data = str(value)

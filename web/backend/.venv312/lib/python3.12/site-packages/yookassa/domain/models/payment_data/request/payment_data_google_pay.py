# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataGooglePay(PaymentData):
    """
    Платежные данные для проведения оплаты при помощи Google Pay.
    """  # noqa: E501

    __payment_method_token = None
    """Криптограмма Payment Token Cryptography для проведения оплаты через Google Pay."""  # noqa: E501

    __google_transaction_id = None
    """Уникальный идентификатор транзакции, выданный Google."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataGooglePay, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.GOOGLE_PAY:
            self.type = PaymentMethodType.GOOGLE_PAY

    @property
    def payment_method_token(self):
        """
        Возвращает payment_method_token модели PaymentDataGooglePay.

        :return: payment_method_token модели PaymentDataGooglePay.
        :rtype: str
        """
        return self.__payment_method_token

    @payment_method_token.setter
    def payment_method_token(self, value):
        """
        Устанавливает payment_method_token модели PaymentDataGooglePay.

        :param value: payment_method_token модели PaymentDataGooglePay.
        :type value: str
        """
        self.__payment_method_token = str(value)

    @property
    def google_transaction_id(self):
        """
        Возвращает google_transaction_id модели PaymentDataGooglePay.

        :return: google_transaction_id модели PaymentDataGooglePay.
        :rtype: str
        """
        return self.__google_transaction_id

    @google_transaction_id.setter
    def google_transaction_id(self, value):
        """
        Устанавливает google_transaction_id модели PaymentDataGooglePay.

        :param value: google_transaction_id модели PaymentDataGooglePay.
        :type value: str
        """
        self.__google_transaction_id = str(value)

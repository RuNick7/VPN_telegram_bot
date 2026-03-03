# -*- coding: utf-8 -*-
from yookassa.domain.request.payment_method_request import PaymentMethodRequest
from yookassa.domain.models.payment_method.request.payment_method_holder import PaymentMethodHolder
from yookassa.domain.models.payment_data.request.credit_card import CreditCard


class PaymentMethodRequestBuilder(object):
    """
    Конструктор запроса для проверки и сохранения способа оплаты.
    """  # noqa: E501

    def __init__(self):
        self.__request = PaymentMethodRequest()

    def set_type(self, value):
        """
        Устанавливает type модели PaymentMethodRequestBuilder.

        :param value: type модели PaymentMethodRequestBuilder.
        :type value: str
        :rtype: PaymentMethodRequestBuilder
        """
        self.__request.type = value
        return self

    def set_card(self, value):
        """
        Устанавливает card модели PaymentMethodRequestBuilder.

        :param value: card модели PaymentMethodRequestBuilder.
        :type value: CreditCard
        :rtype: PaymentMethodRequestBuilder
        """
        self.__request.card = value
        return self

    def set_holder(self, value):
        """
        Устанавливает holder модели PaymentMethodRequestBuilder.

        :param value: holder модели PaymentMethodRequestBuilder.
        :type value: PaymentMethodHolder
        :rtype: PaymentMethodRequestBuilder
        """
        self.__request.holder = value
        return self

    def set_client_ip(self, value):
        """
        Устанавливает client_ip модели PaymentMethodRequestBuilder.

        :param value: client_ip модели PaymentMethodRequestBuilder.
        :type value: str
        :rtype: PaymentMethodRequestBuilder
        """
        self.__request.client_ip = value
        return self

    def set_confirmation(self, value):
        """
        Устанавливает confirmation модели PaymentMethodRequestBuilder.

        :param value: confirmation модели PaymentMethodRequestBuilder.
        :type value: ConfirmationRequest
        :rtype: PaymentMethodRequestBuilder
        """
        self.__request.confirmation = value
        return self

    def build(self):
        """
        Возвращает request модели PaymentMethodRequestBuilder.

        :return: request модели PaymentMethodRequestBuilder.
        :rtype: PaymentMethodRequest
        """
        return self.__request

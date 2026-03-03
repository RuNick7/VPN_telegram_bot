# coding: utf-8
import datetime

from yookassa.domain.request.invoice_request import InvoiceRequest


class InvoiceRequestBuilder(object):
    """Конструктор запроса на создание нового счета."""  # noqa: E501

    def __init__(self):
        self.__request = InvoiceRequest()

    def set_payment_data(self, value):
        """Устанавливает payment_data модели InvoiceRequest.

        :param value: payment_data модели InvoiceRequest.
        :type value: PaymentData
        :rtype: InvoiceRequestBuilder
        """
        self.__request.payment_data = value
        return self

    def set_cart(self, value):
        """Устанавливает cart модели InvoiceRequest.

        :param value: cart модели InvoiceRequest.
        :type value: list[LineItem]
        :rtype: InvoiceRequestBuilder
        """
        self.__request.cart = value
        return self

    def set_delivery_method_data(self, value):
        """Устанавливает delivery_method_data модели InvoiceRequest.

        :param value: delivery_method_data модели InvoiceRequest.
        :type value: DeliveryMethod
        :rtype: InvoiceRequestBuilder
        """
        self.__request.delivery_method_data = value
        return self

    def set_expires_at(self, value):
        """Устанавливает expires_at модели InvoiceRequest.

        :param value: expires_at модели InvoiceRequest.
        :type value: datetime
        :rtype: InvoiceRequestBuilder
        """
        self.__request.expires_at = value
        return self

    def set_locale(self, value):
        """Устанавливает locale модели InvoiceRequest.

        :param value: locale модели InvoiceRequest.
        :type value: str
        :rtype: InvoiceRequestBuilder
        """
        self.__request.locale = value
        return self

    def set_description(self, value):
        """Устанавливает description модели InvoiceRequest.

        :param value: description модели InvoiceRequest.
        :type value: str
        :rtype: InvoiceRequestBuilder
        """
        self.__request.description = value
        return self

    def set_metadata(self, value):
        """Устанавливает metadata модели InvoiceRequest.

        :param value: metadata модели InvoiceRequest.
        :type value: dict[str, str]
        :rtype: InvoiceRequestBuilder
        """
        self.__request.metadata = value

    def build(self):
        """
        Возвращает request модели InvoiceRequestBuilder.

        :return: request модели InvoiceRequestBuilder.
        :rtype: InvoiceRequest
        """
        return self.__request

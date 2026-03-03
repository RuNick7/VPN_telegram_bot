# -*- coding: utf-8 -*-
from yookassa.domain.request.refund_request import RefundRequest


class RefundRequestBuilder(object):
    """
    Конструктор запроса на создание возврата средств.
    """  # noqa: E501

    def __init__(self):
        self.__request = RefundRequest()

    def set_payment_id(self, value):
        """
        Устанавливает payment_id модели RefundRequestBuilder.

        :param value: payment_id модели RefundRequestBuilder.
        :type value: str
        :rtype: RefundRequestBuilder
        """
        self.__request.payment_id = value
        return self

    def set_amount(self, value):
        """
        Устанавливает amount модели RefundRequestBuilder.

        :param value: amount модели RefundRequestBuilder.
        :type value: Amount
        :rtype: RefundRequestBuilder
        """
        self.__request.amount = value
        return self

    def set_description(self, value):
        """
        Устанавливает description модели RefundRequestBuilder.

        :param value: description модели RefundRequestBuilder.
        :type value: str
        :rtype: RefundRequestBuilder
        """
        self.__request.description = value
        return self

    def set_receipt(self, value):
        """
        Устанавливает receipt модели RefundRequestBuilder.

        :param value: receipt модели RefundRequestBuilder.
        :type value: Receipt
        :rtype: RefundRequestBuilder
        """
        self.__request.receipt = value
        return self

    def set_sources(self, value):
        """
        Устанавливает sources модели RefundRequestBuilder.

        :param value: sources модели RefundRequestBuilder.
        :type value: list[RefundSource]
        :rtype: RefundRequestBuilder
        """
        self.__request.sources = value
        return self

    def set_deal(self, value):
        """
        Устанавливает deal модели RefundRequestBuilder.

        :param value: deal модели RefundRequestBuilder.
        :type value: RefundDealData
        :rtype: RefundRequestBuilder
        """
        self.__request.deal = value
        return self

    def refund_method_data(self, value):
        """Устанавливает refund_method_data модели RefundRequestBuilder.

        :param value: refund_method_data модели RefundRequestBuilder.
        :type value: RequestRefundData
        :rtype: RefundRequestBuilder
        """
        self.__request.refund_method_data = value
        return self

    def set_metadata(self, value):
        """
        Устанавливает metadata модели RefundRequestBuilder.

        :param value: metadata модели RefundRequestBuilder.
        :type value: dict[str, str]
        :rtype: PaymentRequestBuilder
        """
        self.__request.metadata = value
        return self

    def build(self):
        """
        Возвращает request модели RefundRequestBuilder.

        :return: request модели RefundRequestBuilder.
        :rtype: RefundRequest
        """
        return self.__request

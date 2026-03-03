# -*- coding: utf-8 -*-
from yookassa.domain.request.capture_payment_request import CapturePaymentRequest


class CapturePaymentBuilder(object):
    """
    Конструктор запроса на подтверждение оплаты.
    """  # noqa: E501

    def __init__(self):
        self.__request = CapturePaymentRequest()

    def set_amount(self, value):
        """
        Устанавливает amount модели CapturePaymentRequest.

        :param value: amount модели CapturePaymentRequest.
        :type value: Amount
        :rtype: CapturePaymentBuilder
        """
        self.__request.amount = value
        return self

    def set_receipt(self, value):
        """
        Устанавливает receipt модели CapturePaymentRequest.

        :param value: receipt модели CapturePaymentRequest.
        :type value: Receipt
        :rtype: CapturePaymentBuilder
        """
        self.__request.receipt = value
        return self

    def set_airline(self, value):
        """
        Устанавливает airline модели CapturePaymentRequest.

        :param value: airline модели CapturePaymentRequest.
        :type value: Airline
        :rtype: CapturePaymentBuilder
        """
        self.__request.airline = value
        return self

    def set_transfers(self, value):
        """
        Устанавливает transfers модели CapturePaymentRequest.

        :param value: transfers модели CapturePaymentRequest.
        :type value: list[Transfer]
        :rtype: CapturePaymentBuilder
        """
        self.__request.transfers = value
        return self

    def set_deal(self, value):
        """
        Устанавливает deal модели CapturePaymentRequest.

        :param value: deal модели CapturePaymentRequest.
        :type value: PaymentDealInfo
        :rtype: CapturePaymentBuilder
        """
        self.__request.deal = value
        return self

    def build(self):
        """
        Возвращает request модели CapturePaymentBuilder.

        :return: request модели CapturePaymentBuilder.
        :rtype: CapturePaymentRequest
        """
        return self.__request

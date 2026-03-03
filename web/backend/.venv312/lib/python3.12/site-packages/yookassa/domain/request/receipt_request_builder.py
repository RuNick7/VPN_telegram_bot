# -*- coding: utf-8 -*-
from yookassa.domain.request.receipt_request import ReceiptRequest


class ReceiptRequestBuilder(object):
    """
    Конструктор запроса на создание чека.
    """  # noqa: E501
    
    def __init__(self):
        self.__request = ReceiptRequest()

    def set_type(self, value):
        """
        Устанавливает type модели ReceiptRequestBuilder.

        :param value: type модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.type = value
        return self

    def set_payment_id(self, value):
        """
        Устанавливает type модели ReceiptRequestBuilder.

        :param value: type модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.payment_id = value
        return self

    def set_refund_id(self, value):
        """
        Устанавливает refund_id модели ReceiptRequestBuilder.

        :param value: refund_id модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.refund_id = value
        return self

    def set_send(self, value):
        """
        Устанавливает send модели ReceiptRequestBuilder.

        :param value: send модели ReceiptRequestBuilder.
        :type value: bool
        :rtype: ReceiptRequestBuilder
        """
        self.__request.send = value
        return self

    def set_customer(self, value):
        """
        Устанавливает customer модели ReceiptRequestBuilder.

        :param value: customer модели ReceiptRequestBuilder.
        :type value: ReceiptCustomer
        :rtype: ReceiptRequestBuilder
        """
        self.__request.customer = value
        return self

    def set_phone(self, value):
        """
        Устанавливает phone модели ReceiptRequestBuilder.

        :param value: phone модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.phone = value
        return self

    def set_email(self, value):
        """
        Устанавливает email модели ReceiptRequestBuilder.

        :param value: email модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.email = value
        return self

    def set_tax_system_code(self, value):
        """
        Устанавливает tax_system_code модели ReceiptRequestBuilder.

        :param value: tax_system_code модели ReceiptRequestBuilder.
        :type value: int
        :rtype: ReceiptRequestBuilder
        """
        self.__request.tax_system_code = value
        return self

    def set_items(self, value):
        """
        Устанавливает items модели ReceiptRequestBuilder.

        :param value: items модели ReceiptRequestBuilder.
        :type value: list[ReceiptItemRequest]
        :rtype: ReceiptRequestBuilder
        """
        self.__request.items = value
        return self

    def set_internet(self, value):
        """
        Устанавливает internet модели ReceiptRequestBuilder.

        :param value: internet модели ReceiptRequestBuilder.
        :type value: bool
        :rtype: ReceiptRequestBuilder
        """
        self.__request.internet = value
        return self

    def set_timezone(self, value):
        """
        Устанавливает timezone модели ReceiptRequestBuilder.

        :param value: timezone модели ReceiptRequestBuilder.
        :type value: int
        :rtype: ReceiptRequestBuilder
        """
        self.__request.timezone = value
        return self

    def set_settlements(self, value):
        """
        Устанавливает settlements модели ReceiptRequestBuilder.

        :param value: settlements модели ReceiptRequestBuilder.
        :type value: list[Settlement]
        :rtype: ReceiptRequestBuilder
        """
        self.__request.settlements = value
        return self

    def set_on_behalf_of(self, value):
        """
        Устанавливает on_behalf_of модели ReceiptRequestBuilder.

        :param value: on_behalf_of модели ReceiptRequestBuilder.
        :type value: str
        :rtype: ReceiptRequestBuilder
        """
        self.__request.on_behalf_of = value
        return self

    def set_receipt_operational_details(self, value):
        """
        Устанавливает receipt_operational_details модели ReceiptRequestBuilder.

        :param value: receipt_operational_details модели ReceiptRequestBuilder.
        :type value: OperationalDetails
        :rtype: ReceiptRequestBuilder
        """
        self.__request.receipt_operational_details = value
        return self

    def set_receipt_industry_details(self, value):
        """
        Устанавливает receipt_industry_details модели ReceiptRequestBuilder.

        :param value: receipt_industry_details модели ReceiptRequestBuilder.
        :type value: list[IndustryDetails]
        :rtype: ReceiptRequestBuilder
        """
        self.__request.receipt_industry_details = value
        return self

    def set_additional_user_props(self, value):
        """
        Устанавливает additional_user_props модели ReceiptRequestBuilder.

        :param value: additional_user_props модели ReceiptRequestBuilder.
        :type value: AdditionalUserProps
        :rtype: ReceiptRequestBuilder
        """
        self.__request.additional_user_props = value
        return self

    def build(self):
        """
        Возвращает request модели ReceiptRequestBuilder.

        :return: request модели ReceiptRequestBuilder.
        :rtype: ReceiptRequest
        """
        return self.__request

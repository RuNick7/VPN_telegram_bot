# -*- coding: utf-8 -*-
from yookassa.domain.request.payment_request import PaymentRequest


class PaymentRequestBuilder(object):
    """
    Конструктор запроса на проведение нового платежа.
    """  # noqa: E501

    def __init__(self):
        self.__request = PaymentRequest()

    def set_recipient(self, value):
        """
        Устанавливает recipient модели PaymentRequestBuilder.

        :param value: recipient модели PaymentRequestBuilder.
        :type value: Recipient
        :rtype: PaymentRequestBuilder
        """
        self.__request.recipient = value
        return self

    def set_amount(self, value):
        """
        Устанавливает amount модели PaymentRequestBuilder.

        :param value: amount модели PaymentRequestBuilder.
        :type value: Amount
        :rtype: PaymentRequestBuilder
        """
        self.__request.amount = value
        return self

    def set_description(self, value):
        """
        Устанавливает description модели PaymentRequestBuilder.

        :param value: description модели PaymentRequestBuilder.
        :type value: str
        :rtype: PaymentRequestBuilder
        """
        self.__request.description = value
        return self

    def set_receipt(self, value):
        """
        Устанавливает receipt модели PaymentRequestBuilder.

        :param value: receipt модели PaymentRequestBuilder.
        :type value: Receipt
        :rtype: PaymentRequestBuilder
        """
        self.__request.receipt = value
        return self

    def set_payment_token(self, value):
        """
        Устанавливает payment_token модели PaymentRequestBuilder.

        :param value: payment_token модели PaymentRequestBuilder.
        :type value: str
        :rtype: PaymentRequestBuilder
        """
        self.__request.payment_token = value
        return self

    def set_payment_method_id(self, value):
        """
        Устанавливает payment_method_id модели PaymentRequestBuilder.

        :param value: payment_method_id модели PaymentRequestBuilder.
        :type value: str
        :rtype: PaymentRequestBuilder
        """
        self.__request.payment_method_id = value
        return self

    def set_payment_method_data(self, value):
        """
        Устанавливает payment_method_data модели PaymentRequestBuilder.

        :param value: payment_method_data модели PaymentRequestBuilder.
        :type value: PaymentData
        :rtype: PaymentRequestBuilder
        """
        self.__request.payment_method_data = value
        return self

    def set_confirmation(self, value):
        """
        Устанавливает confirmation модели PaymentRequestBuilder.

        :param value: confirmation модели PaymentRequestBuilder.
        :type value: Confirmation
        :rtype: PaymentRequestBuilder
        """
        self.__request.confirmation = value
        return self

    def set_save_payment_method(self, value):
        """
        Устанавливает save_payment_method модели PaymentRequestBuilder.

        :param value: save_payment_method модели PaymentRequestBuilder.
        :type value: bool
        :rtype: PaymentRequestBuilder
        """
        self.__request.save_payment_method = value
        return self

    def set_capture(self, value):
        """
        Устанавливает capture модели PaymentRequestBuilder.

        :param value: capture модели PaymentRequestBuilder.
        :type value: bool
        :rtype: PaymentRequestBuilder
        """
        self.__request.capture = value
        return self

    def set_client_ip(self, value):
        """
        Устанавливает client_ip модели PaymentRequestBuilder.

        :param value: client_ip модели PaymentRequestBuilder.
        :type value: str
        :rtype: PaymentRequestBuilder
        """
        self.__request.client_ip = value
        return self

    def set_airline(self, value):
        """
        Устанавливает airline модели PaymentRequestBuilder.

        :param value: airline модели PaymentRequestBuilder.
        :type value: Airline
        :rtype: PaymentRequestBuilder
        """
        self.__request.airline = value
        return self

    def set_metadata(self, value):
        """
        Устанавливает metadata модели PaymentRequestBuilder.

        :param value: metadata модели PaymentRequestBuilder.
        :type value: dict[str, str]
        :rtype: PaymentRequestBuilder
        """
        self.__request.metadata = value
        return self

    def set_transfers(self, value):
        """
        Устанавливает transfers модели PaymentRequestBuilder.

        :param value: transfers модели PaymentRequestBuilder.
        :type value: list[Transfer]
        :rtype: PaymentRequestBuilder
        """
        self.__request.transfers = value
        return self

    def set_deal(self, value):
        """
        Устанавливает deal модели PaymentRequestBuilder.

        :param value: deal модели PaymentRequestBuilder.
        :type value: PaymentDealInfo
        :rtype: PaymentRequestBuilder
        """
        self.__request.deal = value
        return self

    def set_fraud_data(self, value):
        """
        Устанавливает fraud_data модели PaymentRequestBuilder.
        Больше не поддерживается. Вместо него нужно использовать `receiver`

        :param value: fraud_data модели PaymentRequestBuilder.
        :type value: FraudData
        :rtype: PaymentRequestBuilder
        """
        self.__request.fraud_data = value
        return self

    def set_merchant_customer_id(self, value):
        """
        Устанавливает merchant_customer_id модели PaymentRequestBuilder.

        :param value: merchant_customer_id модели PaymentRequestBuilder.
        :type value: str
        :rtype: PaymentRequestBuilder
        """
        self.__request.merchant_customer_id = value
        return self

    def receiver(self, value):
        """
        Устанавливает receiver модели PaymentRequestBuilder.

        :param value: receiver модели PaymentRequestBuilder.
        :type value: Receiver
        :rtype: PaymentRequestBuilder
        """
        self.__request.receiver = value
        return self

    def set_payment_order(self, value):
        """
        Устанавливает payment_order модели PaymentRequestBuilder.

        :param value: payment_order модели PaymentRequestBuilder.
        :type value: PaymentOrder
        :rtype: PaymentRequestBuilder
        """
        self.__request.payment_order = value
        return self

    def set_statements(self, value):
        """
        Устанавливает statements модели PaymentRequestBuilder.

        :param value: statements модели PaymentRequestBuilder.
        :type value: list[Statement]
        :rtype: PaymentRequestBuilder
        """
        self.__request.statements = value
        return self

    def build(self):
        """
        Возвращает request модели PaymentRequestBuilder.

        :return: request модели PaymentRequestBuilder.
        :rtype: PaymentRequest
        """
        return self.__request

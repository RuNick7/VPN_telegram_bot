# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.deal import PaymentDealInfo
from yookassa.domain.models.payment_data.request.airline import Airline
from yookassa.domain.models.receipt import Receipt
from yookassa.domain.models.transfer import Transfer


class CapturePaymentRequest(RequestObject):
    """
    Объект запроса к API на подтверждение оплаты.
    """  # noqa: E501

    __amount = None
    """
    Итоговая сумма, которая спишется с пользователя. Можно указать часть исходной суммы, тогда остаток вернется пользователю.
    Для этого проверьте, что выбранный способ оплаты [поддерживает частичное списание](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-partly).
    Сумма указывается с кодом валюты. Если вы разделяете потоки платежей, валюта платежа должна соответствовать валюте субаккаунта (`recipient.gateway_id`), если не разделяете — валюте аккаунта shopId в личном кабинете).
    """  # noqa: E501

    __receipt = None
    """Данные фискального чека 54-ФЗ."""  # noqa: E501

    __airline = None
    """Объект с данными для продажи авиабилетов . Используется только для платежей банковской картой."""  # noqa: E501

    __transfers = []
    """Данные об актуальном распределении денег — сколько и в какой магазин нужно перевести. Необходимо передавать, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-payments/basics) и подтверждаете часть платежа. """  # noqa: E501

    __deal = None
    """Данные о сделке, в составе которой проходит платеж. Необходимо передавать, если вы проводите Безопасную сделку  и подтверждаете часть платежа."""  # noqa: E501

    @property
    def amount(self):
        """
        Возвращает amount модели CapturePaymentRequest.

        :return: amount модели CapturePaymentRequest.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели CapturePaymentRequest.

        :param value: amount модели CapturePaymentRequest.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def receipt(self):
        """
        Возвращает receipt модели CapturePaymentRequest.

        :return: receipt модели CapturePaymentRequest.
        :rtype: Receipt
        """
        return self.__receipt

    @receipt.setter
    def receipt(self, value):
        """
        Устанавливает receipt модели CapturePaymentRequest.

        :param value: receipt модели CapturePaymentRequest.
        :type value: Receipt
        """
        if isinstance(value, dict):
            self.__receipt = Receipt(value)
        elif isinstance(value, Receipt):
            self.__receipt = value
        else:
            raise TypeError('Invalid receipt value type')

    @property
    def airline(self):
        """
        Возвращает airline модели CapturePaymentRequest.

        :return: airline модели CapturePaymentRequest.
        :rtype: Airline
        """
        return self.__airline

    @airline.setter
    def airline(self, value):
        """
        Устанавливает airline модели CapturePaymentRequest.

        :param value: airline модели CapturePaymentRequest.
        :type value: Airline
        """
        if isinstance(value, dict):
            self.__airline = Airline(value)
        elif isinstance(value, Airline):
            self.__airline = value
        else:
            raise TypeError('Invalid airline type')

    @property
    def transfers(self):
        """
        Возвращает transfers модели CapturePaymentRequest.

        :return: transfers модели CapturePaymentRequest.
        :rtype: list[Transfer]
        """
        return self.__transfers

    @transfers.setter
    def transfers(self, value):
        """
        Устанавливает transfers модели CapturePaymentRequest.

        :param value: transfers модели CapturePaymentRequest.
        :type value: list[Transfer]
        """
        if isinstance(value, list):
            self.__transfers = [Transfer(item) for item in value]
        elif value is None:
            self.__transfers = []
        else:
            raise TypeError('Invalid transfers data type in capture_payment_request.transfers')

    @property
    def deal(self):
        """
        Возвращает deal модели CapturePaymentRequest.

        :return: deal модели CapturePaymentRequest.
        :rtype: PaymentDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели CapturePaymentRequest.

        :param value: deal модели CapturePaymentRequest.
        :type value: PaymentDealInfo
        """
        if isinstance(value, dict):
            self.__deal = PaymentDealInfo(value)
        elif isinstance(value, PaymentDealInfo):
            self.__deal = value
        else:
            raise TypeError('Invalid deal type')

    def validate(self):
        """
        Влидация данных модели CapturePaymentRequest.
        """
        if self.amount:
            value = self.amount.value
            if not value or value <= 0.0:
                self.__set_validation_error('Invalid amount value: ' + str(value))

        if self.receipt is not None and self.receipt.has_items:
            if self.receipt.customer is None:
                self.__set_validation_error('Customer is empty in CapturePaymentRequest.receipt')

            email = self.receipt.customer.email
            phone = self.receipt.customer.phone
            if not email and not phone:
                self.__set_validation_error('Both email and phone values are empty in CapturePaymentRequest.receipt.customer')

            if not self.receipt.tax_system_code and any(not item.vat_code for item in self.receipt.items):
                self.__set_validation_error('Item vat_id and receipt tax_system_id not specified')

        if self.deal is not None and len(self.deal.settlements) == 0:
            self.__set_validation_error('Deal.settlements not specified')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели CapturePaymentRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

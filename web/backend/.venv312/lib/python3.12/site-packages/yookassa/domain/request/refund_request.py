# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.deal import RefundDealData
from yookassa.domain.models.receipt import Receipt
from yookassa.domain.models.refund_data.refund_data import RequestRefundData
from yookassa.domain.models.refund_data.refund_data_factory import RefundDataFactory
from yookassa.domain.models.refund_data.refund_source import RefundSource


class RefundRequest(RequestObject):
    """
    Объект запроса к API для создания возврата.
    """  # noqa: E501

    __payment_id = None
    """Идентификатор платежа в ЮKassa."""  # noqa: E501

    __amount = None
    """
    Сумма, которую нужно вернуть пользователю. Сумма указывается с кодом валюты.
    Если вы разделяете потоки платежей, валюта возврата должна соответствовать валюте субаккаунта, которая была указана для платежа (`recipient.gateway_id`), если не разделяете — валюте аккаунта `shopId` в личном кабинете).
    """  # noqa: E501

    __description = None
    """Комментарий к возврату, основание для возврата денег пользователю."""  # noqa: E501

    __receipt = None
    """Чек возврата."""  # noqa: E501

    __sources = []
    """Данные о том, с какого магазина и какую сумму нужно удержать для проведения возврата. Необходимо передавать, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-payments/basics). Сейчас в этом параметре можно передать данные только одного магазина."""  # noqa: E501

    __deal = None
    """Информация о сделке."""  # noqa: E501

    __refund_method_data = None
    """Детали возврата. Зависят от способа оплаты, который использовался при проведении платежа."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def payment_id(self):
        """
        Возвращает payment_id модели RefundRequest.

        :return: payment_id модели RefundRequest.
        :rtype: str
        """
        return self.__payment_id

    @payment_id.setter
    def payment_id(self, value):
        """
        Устанавливает payment_id модели RefundRequest.

        :param value: payment_id модели RefundRequest.
        :type value: str
        """
        cast_value = str(value)
        if len(cast_value) == 36:
            self.__payment_id = cast_value
        else:
            raise ValueError('Invalid payment id value')

    @property
    def amount(self):
        """
        Возвращает amount модели RefundRequest.

        :return: amount модели RefundRequest.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели RefundRequest.

        :param value: amount модели RefundRequest.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def description(self):
        """
        Возвращает description модели RefundRequest.

        :return: description модели RefundRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели RefundRequest.

        :param value: description модели RefundRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value and len(cast_value) < 256:
            self.__description = cast_value
        else:
            raise ValueError('Invalid commend value')

    @property
    def sources(self):
        """
        Возвращает sources модели RefundRequest.

        :return: sources модели RefundRequest.
        :rtype: list[RefundSource]
        """
        return self.__sources

    @sources.setter
    def sources(self, value):
        """
        Устанавливает sources модели RefundRequest.

        :param value: sources модели RefundRequest.
        :type value: list[RefundSource]
        """
        if isinstance(value, list):
            self.__sources = [RefundSource(item) for item in value]
        elif value is None:
            self.__sources = []
        else:
            raise TypeError('Invalid sources data type in refund_request.sources')

    @property
    def receipt(self):
        """
        Возвращает receipt модели RefundRequest.

        :return: receipt модели RefundRequest.
        :rtype: Receipt
        """
        return self.__receipt

    @receipt.setter
    def receipt(self, value):
        """
        Устанавливает receipt модели RefundRequest.

        :param value: receipt модели RefundRequest.
        :type value: Receipt
        """
        if isinstance(value, dict):
            self.__receipt = Receipt(value)
        elif isinstance(value, Receipt):
            self.__receipt = value
        else:
            raise TypeError('Invalid receipt value type')

    @property
    def deal(self):
        """
        Возвращает deal модели RefundRequest.

        :return: deal модели RefundRequest.
        :rtype: RefundDealData
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели RefundRequest.

        :param value: deal модели RefundRequest.
        :type value: RefundDealData
        """
        if isinstance(value, dict):
            self.__deal = RefundDealData(value)
        elif isinstance(value, RefundDealData):
            self.__deal = value
        else:
            raise TypeError('Invalid deal value type')

    @property
    def refund_method_data(self):
        """Возвращает refund_method_data модели RefundRequest.

        :return: refund_method_data модели RefundRequest.
        :rtype: RequestRefundData
        """
        return self.__refund_method_data

    @refund_method_data.setter
    def refund_method_data(self, value):
        """Устанавливает refund_method_data модели RefundRequest.

        :param value: refund_method_data модели RefundRequest.
        :type value: RequestRefundData
        """
        if isinstance(value, dict):
            self.__refund_method_data = RefundDataFactory().create(value, self.context())
        elif isinstance(value, RequestRefundData):
            self.__refund_method_data = value
        else:
            raise TypeError('Invalid refund_method_data data type in RefundRequest.refund_method_data')

    @property
    def metadata(self):
        """Возвращает metadata модели RefundRequest.

        :return: metadata модели RefundRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели RefundRequest.

        :param value: metadata модели RefundRequest.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

    def validate(self):
        """
        Влидация данных модели RefundRequest.
        """
        if not self.payment_id:
            self.__set_validation_error('Payment id not specified')

        if not self.amount:
            self.__set_validation_error('Amount not specified')

        if self.amount.value <= 0.0:
            self.__set_validation_error('Invalid amount value: ' + str(self.amount.value))

        if self.receipt is not None and self.receipt.has_items:
            if self.receipt.customer is None:
                self.__set_validation_error('Customer is empty in RefundRequest.receipt')

            email = self.receipt.customer.email
            phone = self.receipt.customer.phone
            if not email and not phone:
                self.__set_validation_error('Both email and phone values are empty in RefundRequest.receipt.customer')

            if not self.receipt.tax_system_code and any(not item.vat_code for item in self.receipt.items):
                self.__set_validation_error('Item vat_id and receipt tax_system_id not specified')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели RefundRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

# -*- coding: utf-8 -*-
from yookassa.domain.common import PaymentMethodType
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.models import CancellationDetails
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.deal import RefundDealInfo
from yookassa.domain.models.refund_data.refund_data_class_map import RefundDataClassMap
from yookassa.domain.models.refund_data.refund_data_factory import RefundDataFactory
from yookassa.domain.models.refund_data.refund_source import RefundSource
from yookassa.domain.models.refund_data.response.refund_authorization_details import RefundAuthorizationDetails


class RefundResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о возврате.
    """  # noqa: E501

    __id = None
    """Идентификатор возврата платежа в ЮKassa."""  # noqa: E501

    __payment_id = None
    """Идентификатор платежа в ЮKassa."""  # noqa: E501

    __status = None
    """Статус возврата."""  # noqa: E501

    __cancellation_details = None
    """Комментарий к статусу `canceled`."""  # noqa: E501

    __receipt_registration = None
    """Статус регистрации чека."""  # noqa: E501

    __created_at = None
    """Время создания возврата. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601), например ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __amount = None
    """Сумма возврата."""  # noqa: E501

    __description = None
    """Комментарий, основание для возврата средств покупателю."""  # noqa: E501

    __sources = None
    """Данные о том, с какого магазина и какую сумму нужно удержать для проведения возврата. Присутствует, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-payments/basics)."""  # noqa: E501

    __deal = None
    """Данные о сделке, в составе которой проходит возврат."""  # noqa: E501

    __refund_method = None
    """Детали возврата. Зависят от способа оплаты, который использовался при проведении платежа."""  # noqa: E501

    __refund_authorization_details = None
    """Данные об авторизации возврата. Присутствуют только для возвратов платежей, совершенных этими способами оплаты: банковская карта, Mir Pay."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели RefundResponse.

        :return: id модели RefundResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели RefundResponse.

        :param value: id модели RefundResponse.
        :type value: str
        """
        self.__id = value

    @property
    def payment_id(self):
        """
        Возвращает payment_id модели RefundResponse.

        :return: payment_id модели RefundResponse.
        :rtype: str
        """
        return self.__payment_id

    @payment_id.setter
    def payment_id(self, value):
        """
        Устанавливает payment_id модели RefundResponse.

        :param value: payment_id модели RefundResponse.
        :type value: str
        """
        self.__payment_id = value

    @property
    def status(self):
        """
        Возвращает status модели RefundResponse.

        :return: status модели RefundResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели RefundResponse.

        :param value: status модели RefundResponse.
        :type value: str
        """
        self.__status = value

    @property
    def cancellation_details(self):
        """
        Возвращает cancellation_details модели RefundResponse.

        :return: cancellation_details модели RefundResponse.
        :rtype: CancellationDetails
        """
        return self.__cancellation_details

    @cancellation_details.setter
    def cancellation_details(self, value):
        """
        Устанавливает cancellation_details модели RefundResponse.

        :param value: cancellation_details модели RefundResponse.
        :type value: CancellationDetails
        """
        self.__cancellation_details = CancellationDetails(value)

    @property
    def receipt_registration(self):
        """
        Возвращает receipt_registration модели RefundResponse.

        :return: receipt_registration модели RefundResponse.
        :rtype: str
        """
        return self.__receipt_registration

    @receipt_registration.setter
    def receipt_registration(self, value):
        """
        Устанавливает receipt_registration модели RefundResponse.

        :param value: receipt_registration модели RefundResponse.
        :type value: str
        """
        self.__receipt_registration = value

    @property
    def created_at(self):
        """
        Возвращает created_at модели RefundResponse.

        :return: created_at модели RefundResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели RefundResponse.

        :param value: created_at модели RefundResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def amount(self):
        """
        Возвращает amount модели RefundResponse.

        :return: amount модели RefundResponse.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели RefundResponse.

        :param value: amount модели RefundResponse.
        :type value: Amount
        """
        self.__amount = Amount(value)

    @property
    def description(self):
        """
        Возвращает description модели RefundResponse.

        :return: description модели RefundResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели RefundResponse.

        :param value: description модели RefundResponse.
        :type value: str
        """
        self.__description = value

    @property
    def sources(self):
        """
        Возвращает sources модели RefundResponse.

        :return: sources модели RefundResponse.
        :rtype: list[RefundSource]
        """
        return self.__sources

    @sources.setter
    def sources(self, value):
        """
        Устанавливает sources модели RefundResponse.

        :param value: sources модели RefundResponse.
        :type value: list[RefundSource]
        """
        if isinstance(value, list):
            self.__sources = [RefundSource(item) for item in value]
        else:
            self.__sources = value

    @property
    def deal(self):
        """
        Возвращает deal модели RefundResponse.

        :return: deal модели RefundResponse.
        :rtype: RefundDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели RefundResponse.

        :param value: deal модели RefundResponse.
        :type value: RefundDealInfo
        """
        self.__deal = RefundDealInfo(value)

    @property
    def refund_method(self):
        """
        Возвращает refund_method модели RefundResponse.

        :return: refund_method модели RefundResponse.
        :rtype: ResponseRefundData
        """
        return self.__refund_method

    @refund_method.setter
    def refund_method(self, value):
        """
        Устанавливает refund_method модели RefundResponse.

        :param value: refund_method модели RefundResponse.
        :type value: ResponseRefundData
        """
        if isinstance(value, dict) and 'type' in value and value['type'] not in RefundDataClassMap().response:
            value['type'] = PaymentMethodType.UNKNOWN
        self.__refund_method = RefundDataFactory().create(value, self.context())

    @property
    def refund_authorization_details(self):
        """Возвращает refund_authorization_details модели RefundResponse.

        :return: refund_authorization_details модели RefundResponse.
        :rtype: RefundAuthorizationDetails
        """
        return self.__refund_authorization_details

    @refund_authorization_details.setter
    def refund_authorization_details(self, value):
        """Устанавливает refund_authorization_details модели RefundResponse.

        :param value: refund_authorization_details модели RefundResponse.
        :type value: RefundAuthorizationDetails
        """
        self.__refund_authorization_details = RefundAuthorizationDetails(value)

    @property
    def metadata(self):
        """Возвращает metadata модели Refund.

        :return: metadata модели Refund.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели Refund.

        :param value: metadata модели Refund.
        :type value: dict[str, str]
        """
        self.__metadata = value

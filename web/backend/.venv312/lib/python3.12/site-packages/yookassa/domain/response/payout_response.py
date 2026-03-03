# -*- coding: utf-8 -*-
from yookassa.domain.common import ResponseObject, PaymentMethodType
from yookassa.domain.models import Amount, CancellationDetails
from yookassa.domain.models.deal import PayoutDealInfo
from yookassa.domain.models.payout_data.payout_destination_factory import PayoutDestinationFactory
from yookassa.domain.models.payout_data.payout_destination_class_map import PayoutDestinationClassMap
from yookassa.domain.models.payout_data.response.income_receipt import IncomeReceipt
from yookassa.domain.models.self_employed import PayoutSelfEmployed


class PayoutResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе конкретной выплаты.
    """  # noqa: E501

    __id = None
    """Идентификатор выплаты."""  # noqa: E501

    __amount = None
    """Сумма выплаты."""  # noqa: E501

    __status = None
    """Текущее состояние выплаты."""  # noqa: E501

    __payout_destination = None
    """Способ проведения выплаты."""  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов). Например: «Выплата по договору 37». """  # noqa: E501

    __created_at = None
    """Время создания выплаты. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __succeeded_at = None
    """Время успешного проведения выплаты. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:42.312Z`  Обязательный параметр для выплат в статусе ~`succeeded`. """  # noqa: E501

    __deal = None
    """Сделка, в рамках которой нужно провести выплату."""  # noqa: E501

    __self_employed = None
    """Данные самозанятого, который получит выплату."""  # noqa: E501

    __receipt = None
    """Данные чека, зарегистрированного в ФНС."""  # noqa: E501

    __cancellation_details = None
    """Комментарий к отмене выплаты."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __test = None
    """Признак тестовой операции."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PayoutResponse.

        :return: id модели PayoutResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PayoutResponse.

        :param value: id модели PayoutResponse.
        :type value: str
        """
        self.__id = value

    @property
    def amount(self):
        """
        Возвращает amount модели PayoutResponse.

        :return: amount модели PayoutResponse.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели PayoutResponse.

        :param value: amount модели PayoutResponse.
        :type value: Amount
        """
        self.__amount = Amount(value)

    @property
    def status(self):
        """
        Возвращает status модели PayoutResponse.

        :return: status модели PayoutResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели PayoutResponse.

        :param value: status модели PayoutResponse.
        :type value: str
        """
        self.__status = value

    @property
    def payout_destination(self):
        """
        Возвращает payout_destination модели PayoutResponse.

        :return: payout_destination модели PayoutResponse.
        :rtype: PayoutDestination
        """
        return self.__payout_destination

    @payout_destination.setter
    def payout_destination(self, value):
        """
        Устанавливает payout_destination модели PayoutResponse.

        :param value: payout_destination модели PayoutResponse.
        :type value: PayoutDestination
        """
        if isinstance(value, dict) and 'type' in value and value['type'] not in PayoutDestinationClassMap().response:
            value['type'] = PaymentMethodType.UNKNOWN
        self.__payout_destination = PayoutDestinationFactory().create(value, self.context())

    @property
    def description(self):
        """
        Возвращает description модели PayoutResponse.

        :return: description модели PayoutResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели PayoutResponse.

        :param value: description модели PayoutResponse.
        :type value: str
        """
        self.__description = value

    @property
    def created_at(self):
        """
        Возвращает created_at модели PayoutResponse.

        :return: created_at модели PayoutResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели PayoutResponse.

        :param value: created_at модели PayoutResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def succeeded_at(self):
        """Возвращает succeeded_at модели PayoutResponse.

        :return: succeeded_at модели PayoutResponse.
        :rtype: datetime
        """
        return self.__succeeded_at

    @succeeded_at.setter
    def succeeded_at(self, value):
        """Устанавливает succeeded_at модели PayoutResponse.

        :param value: succeeded_at модели PayoutResponse.
        :type value: datetime
        """
        self.__succeeded_at = value

    @property
    def deal(self):
        """
        Возвращает deal модели PayoutResponse.

        :return: deal модели PayoutResponse.
        :rtype: PayoutDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели PayoutResponse.

        :param value: deal модели PayoutResponse.
        :type value: PayoutDealInfo
        """
        self.__deal = PayoutDealInfo(value)

    @property
    def self_employed(self):
        """
        Возвращает self_employed модели PayoutResponse.

        :return: self_employed модели PayoutResponse.
        :rtype: PayoutSelfEmployed
        """
        return self.__self_employed

    @self_employed.setter
    def self_employed(self, value):
        """
        Устанавливает self_employed модели PayoutResponse.

        :param value: self_employed модели PayoutResponse.
        :type value: PayoutSelfEmployed
        """
        self.__self_employed = PayoutSelfEmployed(value)

    @property
    def receipt(self):
        """
        Возвращает receipt модели PayoutResponse.

        :return: receipt модели PayoutResponse.
        :rtype: IncomeReceipt
        """
        return self.__receipt

    @receipt.setter
    def receipt(self, value):
        """
        Устанавливает receipt модели PayoutResponse.

        :param value: receipt модели PayoutResponse.
        :type value: IncomeReceipt
        """
        self.__receipt = IncomeReceipt(value)

    @property
    def cancellation_details(self):
        """
        Возвращает cancellation_details модели PayoutResponse.

        :return: cancellation_details модели PayoutResponse.
        :rtype: CancellationDetails
        """
        return self.__cancellation_details

    @cancellation_details.setter
    def cancellation_details(self, value):
        """
        Устанавливает cancellation_details модели PayoutResponse.

        :param value: cancellation_details модели PayoutResponse.
        :type value: CancellationDetails
        """
        self.__cancellation_details = CancellationDetails(value)

    @property
    def metadata(self):
        """
        Возвращает metadata модели PayoutResponse.

        :return: metadata модели PayoutResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PayoutResponse.

        :param value: metadata модели PayoutResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

    @property
    def test(self):
        """
        Возвращает test модели PayoutResponse.

        :return: test модели PayoutResponse.
        :rtype: bool
        """
        return self.__test

    @test.setter
    def test(self, value):
        """
        Устанавливает test модели PayoutResponse.

        :param value: test модели PayoutResponse.
        :type value: bool
        """
        self.__test = bool(value)

# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.deal import PayoutDealInfo
from yookassa.domain.models.payout_data.payout_destination import PayoutDestination
from yookassa.domain.models.payout_data.payout_destination_factory import PayoutDestinationFactory
from yookassa.domain.models.personal_data import PayoutPersonalData

DESCRIPTION_MAX_LENGTH = 128


class PayoutRequest(RequestObject):
    """
    Объект запроса к API на проведение новой выплаты.
    """  # noqa: E501

    __amount = None
    """Сумма создаваемой выплаты."""  # noqa: E501

    __payout_destination_data = None
    """Данные платежного средства, на которое нужно сделать выплату. Обязательный параметр, если не передан payout_token."""  # noqa: E501

    __payout_token = None
    """Токенизированные данные для выплаты. Например, синоним банковской карты. Обязательный параметр, если не передан `payout_destination_data` или `payment_method_id`. """  # noqa: E501

    __payment_method_id = None
    """Идентификатор сохраненного способа оплаты, данные которого нужно использовать для проведения выплаты."""  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов). Например: «Выплата по договору 37». """  # noqa: E501

    __deal = None
    """Сделка, в рамках которой нужно провести выплату. Необходимо передавать, если вы проводите Безопасную сделку."""  # noqa: E501

    __self_employed = None
    """Данные самозанятого, который получит выплату. Необходимо передавать, если вы делаете выплату [самозанятому](https://yookassa.ru/developers/payouts/scenario-extensions/self-employed). Только для обычных выплат."""  # noqa: E501

    __receipt_data = None
    """Данные для формирования чека в сервисе Мой налог. Необходимо передавать, если вы делаете выплату [самозанятому](https://yookassa.ru/developers/payouts/scenario-extensions/self-employed). Только для обычных выплат."""  # noqa: E501

    __personal_data = None
    """Персональные данные получателя выплаты. Необходимо передавать, если вы делаете выплаты с %[проверкой получателя](/developers/payouts/scenario-extensions/recipient-check) (только для выплат через СБП). """  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def amount(self):
        """
        Возвращает amount модели PayoutRequest.

        :return: amount модели PayoutRequest.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели PayoutRequest.

        :param value: amount модели PayoutRequest.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def payout_destination_data(self):
        """
        Возвращает payout_destination_data модели PayoutRequest.

        :return: payout_destination_data модели PayoutRequest.
        :rtype: PayoutDestination
        """
        return self.__payout_destination_data

    @payout_destination_data.setter
    def payout_destination_data(self, value):
        """
        Устанавливает payout_destination_data модели PayoutRequest.

        :param value: payout_destination_data модели PayoutRequest.
        :type value: PayoutDestination
        """
        if isinstance(value, dict):
            self.__payout_destination_data = PayoutDestinationFactory().create(value, self.context())
        elif isinstance(value, PayoutDestination):
            self.__payout_destination_data = value
        else:
            raise TypeError('Invalid payout_destination_data type')

    @property
    def payout_token(self):
        """
        Возвращает payout_token модели PayoutRequest.

        :return: payout_token модели PayoutRequest.
        :rtype: str
        """
        return self.__payout_token

    @payout_token.setter
    def payout_token(self, value):
        """
        Устанавливает payout_token модели PayoutRequest.

        :param value: payout_token модели PayoutRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__payout_token = cast_value
        else:
            raise TypeError('Invalid payout_token value')

    @property
    def payment_method_id(self):
        """
        Возвращает payment_method_id модели PayoutRequest.

        :return: payment_method_id модели PayoutRequest.
        :rtype: str
        """
        return self.__payment_method_id

    @payment_method_id.setter
    def payment_method_id(self, value):
        """
        Устанавливает payment_method_id модели PayoutRequest.

        :param value: payment_method_id модели PayoutRequest.
        :type value: str
        """
        self.__payment_method_id = value

    @property
    def description(self):
        """
        Возвращает description модели PayoutRequest.

        :return: description модели PayoutRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели PayoutRequest.

        :param value: description модели PayoutRequest.
        :type value: str
        """
        cast_value = str(value)
        if len(cast_value) <= DESCRIPTION_MAX_LENGTH:
            self.__description = cast_value
        else:
            raise ValueError('The value of the description parameter is too long. Max length is {}'.format(DESCRIPTION_MAX_LENGTH))  # noqa: E501

    @property
    def deal(self):
        """
        Возвращает deal модели PayoutRequest.

        :return: deal модели PayoutRequest.
        :rtype: PayoutDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели PayoutRequest.

        :param value: deal модели PayoutRequest.
        :type value: PayoutDealInfo
        """
        if isinstance(value, dict):
            self.__deal = PayoutDealInfo(value)
        elif isinstance(value, PayoutDealInfo):
            self.__deal = value
        else:
            raise TypeError('Invalid deal type')

    @property
    def self_employed(self):
        """
        Возвращает self_employed модели PayoutRequest.
        Больше не используется.
        """
        return None

    @self_employed.setter
    def self_employed(self, value):
        """
        Устанавливает self_employed модели PayoutRequest.
        Больше не используется.
        """

    @property
    def receipt_data(self):
        """
        Возвращает receipt_data модели PayoutRequest.
        Больше не используется.
        """
        return None

    @receipt_data.setter
    def receipt_data(self, value):
        """
        Устанавливает receipt_data модели PayoutRequest.
        Больше не используется.
        """

    @property
    def personal_data(self):
        """
        Возвращает personal_data модели PayoutRequest.

        :return: personal_data модели PayoutRequest.
        :rtype: list[PayoutPersonalData]
        """
        return self.__personal_data

    @personal_data.setter
    def personal_data(self, value):
        """
        Устанавливает personal_data модели PayoutRequest.

        :param value: personal_data модели PayoutRequest.
        :type value: list[PayoutPersonalData]
        """
        if isinstance(value, list):
            if len(value) > 2:
                raise ValueError("Invalid value for `personal_data`, number of items must be less than or equal to `2`")  # noqa: E501
            if len(value) < 1:
                raise ValueError("Invalid value for `personal_data`, number of items must be greater than or equal to `1`")  # noqa: E501

            personal_data_array = []
            for personal_dataData in value:
                if isinstance(personal_dataData, dict):
                    personal_data_array.append(PayoutPersonalData(personal_dataData))
                elif isinstance(personal_dataData, PayoutPersonalData):
                    personal_data_array.append(personal_dataData)
                else:
                    raise TypeError('Invalid personal_data data type in PayoutRequest.personal_data')
            self.__personal_data = personal_data_array
        else:
            raise TypeError('Invalid personal_data value type in PayoutRequest')

    @property
    def metadata(self):
        """
        Возвращает metadata модели PayoutRequest.

        :return: metadata модели PayoutRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PayoutRequest.

        :param value: metadata модели PayoutRequest.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

    def validate(self):
        """
        Влидация данных модели PayoutRequest.
        """
        amount = self.amount
        if amount is None:
            self.__set_validation_error('Payout amount not specified')

        if amount.value <= 0.0:
            self.__set_validation_error('Invalid payout amount value: ' + str(amount.value))

        if (self.payout_token and self.payout_destination_data) or \
                (self.payout_token and self.payment_method_id) or \
                (self.payout_destination_data and self.payment_method_id):
            self.__set_validation_error('Both payout_token, payout_destination_data and payment_method_id values are specified')

        elif self.payout_token is None and self.payout_destination_data is None and self.payment_method_id is None:
            self.__set_validation_error('Both payout_token, payout_destination_data and payment_method_id values are not specified')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели PayoutRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

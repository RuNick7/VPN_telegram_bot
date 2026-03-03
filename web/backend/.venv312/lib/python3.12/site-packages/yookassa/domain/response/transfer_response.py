# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount


class TransferResponse(BaseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о распределении денег — сколько и в какой магазин нужно перевести.
    """  # noqa: E501

    __account_id = None
    """Идентификатор магазина, в пользу которого вы принимаете оплату."""  # noqa: E501

    __amount = None
    """Сумма, которую необходимо перечислить магазину."""  # noqa: E501

    __status = None
    """Статус распределения денег между магазинами. """  # noqa: E501

    __platform_fee_amount = None
    """Комиссия за проданные товары и услуги, которая удерживается с магазина в вашу пользу."""  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов), которое продавец увидит в личном кабинете ЮKassa. Например: «Заказ маркетплейса №72». """  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __release_funds = None
    """Порядок перевода денег продавцам: ~`true` — перевести сразу, ~`false` — сначала захолдировать. """  # noqa: E501

    __connected_account_id = None
    """Идентификатор продавца, подключенного к вашей платформе."""  # noqa: E501

    @property
    def account_id(self):
        """
        Возвращает account_id модели TransferResponse.

        :return: account_id модели TransferResponse.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """
        Устанавливает account_id модели TransferResponse.

        :param value: account_id модели TransferResponse.
        :type value: str
        """
        self.__account_id = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели TransferResponse.

        :return: amount модели TransferResponse.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели TransferResponse.

        :param value: amount модели TransferResponse.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def status(self):
        """
        Возвращает status модели TransferResponse.

        :return: status модели TransferResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели TransferResponse.

        :param value: status модели TransferResponse.
        :type value: str
        """
        self.__status = str(value)

    @property
    def platform_fee_amount(self):
        """
        Возвращает platform_fee_amount модели TransferResponse.

        :return: platform_fee_amount модели TransferResponse.
        :rtype: Amount
        """
        return self.__platform_fee_amount

    @platform_fee_amount.setter
    def platform_fee_amount(self, value):
        """
        Устанавливает platform_fee_amount модели TransferResponse.

        :param value: platform_fee_amount модели TransferResponse.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__platform_fee_amount = Amount(value)
        elif isinstance(value, Amount):
            self.__platform_fee_amount = value
        else:
            raise TypeError('Invalid platform_fee_amount value type')

    @property
    def description(self):
        """
        Возвращает description модели TransferResponse.

        :return: description модели TransferResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели TransferResponse.

        :param value: description модели TransferResponse.
        :type value: str
        """
        self.__description = str(value)

    @property
    def metadata(self):
        """
        Возвращает metadata модели TransferResponse.

        :return: metadata модели TransferResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели TransferResponse.

        :param value: metadata модели TransferResponse.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

    @property
    def release_funds(self):
        """
        Возвращает release_funds модели TransferResponse.

        :return: release_funds модели TransferResponse.
        :rtype: bool
        """
        return self.__release_funds

    @release_funds.setter
    def release_funds(self, value):
        """
        Устанавливает release_funds модели TransferResponse.

        :param value: release_funds модели TransferResponse.
        :type value: bool
        """
        self.__release_funds = value

    @property
    def connected_account_id(self):
        """
        Возвращает connected_account_id модели TransferResponse.

        :return: connected_account_id модели TransferResponse.
        :rtype: str
        """
        return self.__connected_account_id

    @connected_account_id.setter
    def connected_account_id(self, value):
        """
        Устанавливает connected_account_id модели TransferResponse.

        :param value: connected_account_id модели TransferResponse.
        :type value: str
        """
        self.__connected_account_id = value


class TransferStatus(object):
    """
    Статус распределения денег между магазинами. 
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PENDING = 'pending'
    """Ожидает оплаты покупателем."""
    WAITING_FOR_CAPTURE = 'waiting_for_capture'
    """Успешно оплачен покупателем, ожидает подтверждения магазином (capture или aviso)."""
    SUCCEEDED = 'succeeded'
    """Успешно оплачен и получен магазином."""
    CANCELED = 'canceled'
    """Неуспех оплаты или отменен магазином (cancel)."""

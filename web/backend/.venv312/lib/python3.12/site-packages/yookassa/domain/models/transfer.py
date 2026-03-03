# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount

DESCRIPTION_MAX_LENGTH = 128


class Transfer(BaseObject):
    """
    Данные о распределении денег — сколько и в какой магазин нужно перевести. Необходимо передавать, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-payments/basics).
    """  # noqa: E501

    __account_id = None
    """Идентификатор магазина, в пользу которого вы принимаете оплату."""  # noqa: E501

    __amount = None
    """Сумма, которую необходимо перечислить магазину."""  # noqa: E501

    __platform_fee_amount = None
    """Комиссия за проданные товары и услуги, которая удерживается с магазина в вашу пользу."""  # noqa: E501

    __description = None
    """Описание транзакции, которое продавец увидит в личном кабинете ЮKassa. (например: «Заказ маркетплейса №72»)."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы с платежами (например, ваш внутренний идентификатор заказа)."""  # noqa: E501

    @property
    def account_id(self):
        """
        Возвращает account_id модели Transfer.

        :return: account_id модели Transfer.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """
        Устанавливает account_id модели Transfer.

        :param value: account_id модели Transfer.
        :type value: str
        """
        self.__account_id = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели Transfer.

        :return: amount модели Transfer.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели Transfer.

        :param value: amount модели Transfer.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid transfer.amount value type')

    @property
    def platform_fee_amount(self):
        """
        Возвращает platform_fee_amount модели Transfer.

        :return: platform_fee_amount модели Transfer.
        :rtype: Amount
        """
        return self.__platform_fee_amount

    @platform_fee_amount.setter
    def platform_fee_amount(self, value):
        """
        Устанавливает platform_fee_amount модели Transfer.

        :param value: platform_fee_amount модели Transfer.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__platform_fee_amount = Amount(value)
        elif isinstance(value, Amount):
            self.__platform_fee_amount = value
        else:
            raise TypeError('Invalid transfer.platform_fee_amount value type')

    @property
    def description(self):
        """
        Возвращает description модели Transfer.

        :return: description модели Transfer.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели Transfer.

        :param value: description модели Transfer.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            if len(cast_value) <= DESCRIPTION_MAX_LENGTH:
                self.__description = cast_value
            else:
                raise ValueError('The value of the description parameter is too long. Max length is {}'.format(DESCRIPTION_MAX_LENGTH))  # noqa: E501

    @property
    def metadata(self):
        """
        Возвращает metadata модели Transfer.

        :return: metadata модели Transfer.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели Transfer.

        :param value: metadata модели Transfer.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

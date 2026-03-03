# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class Recipient(BaseObject):
    """
    Получатель платежа. Нужен, если вы разделяете потоки платежей в рамках одного аккаунта или создаете платеж в адрес другого аккаунта.
    """  # noqa: E501

    __account_id = None
    """Идентификатор магазина в ЮKassa."""  # noqa: E501

    __gateway_id = None
    """Идентификатор субаккаунта. Используется для разделения потоков платежей в рамках одного аккаунта."""  # noqa: E501

    @property
    def account_id(self):
        """
        Возвращает account_id модели Recipient.

        :return: account_id модели Recipient.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """
        Устанавливает account_id модели Recipient.

        :param value: account_id модели Recipient.
        :type value: str
        """
        self.__account_id = str(value)

    @property
    def gateway_id(self):
        """
        Возвращает gateway_id модели Recipient.

        :return: gateway_id модели Recipient.
        :rtype: str
        """
        return self.__gateway_id

    @gateway_id.setter
    def gateway_id(self, value):
        """
        Устанавливает gateway_id модели Recipient.

        :param value: gateway_id модели Recipient.
        :type value: str
        """
        self.__gateway_id = str(value)

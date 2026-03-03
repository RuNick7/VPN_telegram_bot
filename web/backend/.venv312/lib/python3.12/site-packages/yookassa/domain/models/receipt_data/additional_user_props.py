# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class AdditionalUserProps(BaseObject):
    """
    Дополнительный реквизит пользователя (тег в 54 ФЗ — 1084). <br/>Можно передавать, если вы отправляете данные для формирования чека по сценарию %[Сначала платеж, потом чек](/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment) 
    """  # noqa: E501

    __name = None
    """Наименование дополнительного реквизита пользователя (тег в 54 ФЗ — 1085). Не более 64 символов. """  # noqa: E501

    __value = None
    """Значение дополнительного реквизита пользователя (тег в 54 ФЗ — 1086). Не более 234 символов. """  # noqa: E501

    @property
    def name(self):
        """
        Возвращает name модели AdditionalUserProps.

        :return: name модели AdditionalUserProps.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Устанавливает name модели AdditionalUserProps.

        :param value: name модели AdditionalUserProps.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 64:
            raise ValueError("Invalid value for `name`, length must be less than or equal to `64`")  # noqa: E501
        self.__name = value

    @property
    def value(self):
        """
        Возвращает value модели AdditionalUserProps.

        :return: value модели AdditionalUserProps.
        :rtype: str
        """
        return self.__value

    @value.setter
    def value(self, value):
        """
        Устанавливает value модели AdditionalUserProps.

        :param value: value модели AdditionalUserProps.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `value`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 234:
            raise ValueError("Invalid value for `value`, length must be less than or equal to `234`")  # noqa: E501
        self.__value = value

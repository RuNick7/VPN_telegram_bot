# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class CreditCard(BaseObject):
    """
    Данные банковской карты.
    """  # noqa: E501

    __first6 = None
    """Первые 6 цифр номера карты."""  # noqa: E501

    __last4 = None
    """Последние 4 цифры номера карты."""  # noqa: E501

    __card_type = None
    """Тип банковской карты."""  # noqa: E501

    __issuer_country = None
    """Код страны, в которой выпущена карта. Передается в формате [ISO-3166 alpha-2](https://www.iso.org/obp/ui/#iso:pub:PUB500001:en). Пример: ~`RU`. """  # noqa: E501

    __issuer_name = None
    """Наименование банка, выпустившего карту."""  # noqa: E501

    @property
    def first6(self):
        """
        Возвращает first6 модели CreditCard.

        :return: first6 модели CreditCard.
        :rtype: str
        """
        return self.__first6

    @first6.setter
    def first6(self, value):
        """
        Устанавливает first6 модели CreditCard.

        :param value: first6 модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{6}$', cast_value):
            self.__first6 = cast_value
        else:
            raise ValueError('Invalid first6 value')

    @property
    def last4(self):
        """
        Возвращает last4 модели CreditCard.

        :return: last4 модели CreditCard.
        :rtype: str
        """
        return self.__last4

    @last4.setter
    def last4(self, value):
        """
        Устанавливает last4 модели CreditCard.

        :param value: last4 модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^[\d]{4}$', cast_value):
            self.__last4 = cast_value
        else:
            raise ValueError('Invalid last4 value')

    @property
    def card_type(self):
        """
        Возвращает card_type модели CreditCard.

        :return: card_type модели CreditCard.
        :rtype: str
        """
        return self.__card_type

    @card_type.setter
    def card_type(self, value):
        """
        Устанавливает card_type модели CreditCard.

        :param value: card_type модели CreditCard.
        :type value: str
        """
        self.__card_type = value

    @property
    def issuer_country(self):
        """
        Возвращает issuer_country модели CreditCard.

        :return: issuer_country модели CreditCard.
        :rtype: str
        """
        return self.__issuer_country

    @issuer_country.setter
    def issuer_country(self, value):
        """
        Устанавливает issuer_country модели CreditCard.

        :param value: issuer_country модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if len(cast_value) == 2:
            self.__issuer_country = cast_value
        else:
            raise ValueError('Invalid card issuer country value')

    @property
    def issuer_name(self):
        """
        Возвращает issuer_name модели CreditCard.

        :return: issuer_name модели CreditCard.
        :rtype: str
        """
        return self.__issuer_name

    @issuer_name.setter
    def issuer_name(self, value):
        """
        Устанавливает issuer_name модели CreditCard.

        :param value: issuer_name модели CreditCard.
        :type value: str
        """
        self.__issuer_name = str(value)

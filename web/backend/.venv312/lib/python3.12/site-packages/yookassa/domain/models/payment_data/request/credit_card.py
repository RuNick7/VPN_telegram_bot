# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class CreditCard(BaseObject):
    """
    Данные банковской карты (необходимы, если вы собираете данные карты пользователей на своей стороне).
    """  # noqa: E501

    __number = None
    """Номер банковской карты."""  # noqa: E501

    __expiry_year = None
    """Срок действия, год, YYYY."""  # noqa: E501

    __expiry_month = None
    """Срок действия, месяц, MM."""  # noqa: E501

    __csc = None
    """Код CVC2 или CVV2, 3 или 4 символа, печатается на обратной стороне карты."""  # noqa: E501

    __cardholder = None
    """Имя владельца карты."""  # noqa: E501

    @property
    def number(self):
        """
        Возвращает number модели CreditCard.

        :return: number модели CreditCard.
        :rtype: str
        """
        return self.__number

    @number.setter
    def number(self, value):
        """
        Устанавливает number модели CreditCard.

        :param value: number модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^[0-9]{14,19}$', cast_value):
            self.__number = cast_value
        else:
            raise ValueError('Invalid card number value')

    @property
    def expiry_year(self):
        """
        Возвращает expiry_year модели CreditCard.

        :return: expiry_year модели CreditCard.
        :rtype: str
        """
        return self.__expiry_year

    @expiry_year.setter
    def expiry_year(self, value):
        """
        Устанавливает expiry_year модели CreditCard.

        :param value: expiry_year модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^\d\d\d\d$', cast_value) and 2000 < int(cast_value) < 2200:
            self.__expiry_year = cast_value
        else:
            raise ValueError('Invalid card expiry year value')

    @property
    def expiry_month(self):
        """
        Возвращает expiry_month модели CreditCard.

        :return: expiry_month модели CreditCard.
        :rtype: str
        """
        return self.__expiry_month

    @expiry_month.setter
    def expiry_month(self, value):
        """
        Устанавливает expiry_month модели CreditCard.

        :param value: expiry_month модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^\d\d$', cast_value) and 0 < int(cast_value) <= 12:
            self.__expiry_month = cast_value
        else:
            raise ValueError('Invalid card expiry month value')

    @property
    def csc(self):
        """
        Возвращает csc модели CreditCard.

        :return: csc модели CreditCard.
        :rtype: str
        """
        return self.__csc

    @csc.setter
    def csc(self, value):
        """
        Устанавливает csc модели CreditCard.

        :param value: csc модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^\d{3,4}$', cast_value):
            self.__csc = cast_value
        else:
            raise ValueError('Invalid card CSC code value')

    @property
    def cardholder(self):
        """
        Возвращает cardholder модели CreditCard.

        :return: cardholder модели CreditCard.
        :rtype: str
        """
        return self.__cardholder

    @cardholder.setter
    def cardholder(self, value):
        """
        Устанавливает cardholder модели CreditCard.

        :param value: cardholder модели CreditCard.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r'^[a-zA-Z \'-]{0,26}$', cast_value):
            self.__cardholder = cast_value
        else:
            raise ValueError('Invalid card holder value')

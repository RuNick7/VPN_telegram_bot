# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class CreditCard(BaseObject):
    """
    Данные банковской карты для выплаты.
    """  # noqa: E501

    __number = None
    """Номер банковской карты. Формат: только цифры, без пробелов. Пример: ~`5555555555554477` """  # noqa: E501

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
        if re.match(r'^[0-9]{16,19}$', cast_value):
            self.__number = cast_value
        else:
            raise ValueError('Invalid card number value')

# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP

from yookassa.domain.common import BaseObject


class Amount(BaseObject):
    """
    Сумма определенная в валюте.
    """  # noqa: E501

    __value = None
    """Сумма в выбранной валюте. Всегда дробное значение. Разделитель дробной части — точка, разделитель тысяч отсутствует. Количество знаков после точки зависит от выбранной валюты. Пример: ~`1000.00`. """  # noqa: E501

    __currency = None
    """Трехбуквенный код валюты в формате ISO-4217. Пример: RUB."""  # noqa: E501

    @property
    def value(self):
        """
        Возвращает value модели Amount.

        :return: value модели Amount.
        :rtype: Decimal
        """
        return self.__value

    @value.setter
    def value(self, value):
        """
        Устанавливает value модели Amount.

        :param value: value модели Amount.
        :type value: Decimal
        """
        self.__value = Decimal(str(float(value))).quantize(Decimal('1.11'), rounding=ROUND_HALF_UP)

    @property
    def currency(self):
        """
        Возвращает currency модели Amount.

        :return: currency модели Amount.
        :rtype: str
        """
        return self.__currency

    @currency.setter
    def currency(self, value):
        """
        Устанавливает currency модели Amount.

        :param value: currency модели Amount.
        :type value: str
        """
        self.__currency = str(value)

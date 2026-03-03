# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PaymentPeriod(BaseObject):
    """Период оплаты, за который выставлены начисления и за который вносится оплата."""  # noqa: E501

    __month = None
    """Месяц периода. Например, ~`1` — январь. """  # noqa: E501

    __year = None
    """Год периода. Значение должно быть в диапазоне 1920–2050. Например, ~`2025`. """  # noqa: E501

    @property
    def month(self):
        """Возвращает month модели PaymentPeriod.

        :return: month модели PaymentPeriod.
        :rtype: int
        """
        return self.__month

    @month.setter
    def month(self, value):
        """Устанавливает month модели PaymentPeriod.

        :param value: month модели PaymentPeriod.
        :type value: int
        """
        if value is not None and value > 12:  # noqa: E501
            raise ValueError("Invalid value for `month`, must be a value less than or equal to `12`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `month`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__month = value

    @property
    def year(self):
        """Возвращает year модели PaymentPeriod.

        :return: year модели PaymentPeriod.
        :rtype: int
        """
        return self.__year

    @year.setter
    def year(self, value):
        """Устанавливает year модели PaymentPeriod.

        :param value: year модели PaymentPeriod.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `year`, must not be `None`")  # noqa: E501
        if value is not None and value > 2050:  # noqa: E501
            raise ValueError("Invalid value for `year`, must be a value less than or equal to `2050`")  # noqa: E501
        if value is not None and value < 1920:  # noqa: E501
            raise ValueError("Invalid value for `year`, must be a value greater than or equal to `1920`")  # noqa: E501
        self.__year = value

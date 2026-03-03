# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class MarkQuantity(BaseObject):
    """
    Дробное количество маркированного товара (тег в 54 ФЗ — 1291). Обязательный параметр, если одновременно выполняются эти условия:
      * вы используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2;
      * товар нужно [маркировать](http://docs.cntd.ru/document/902192509);
      * поле `measure` имеет значение ~`piece`.

    Пример: вы продаете поштучно карандаши. Они поставляются пачками по 100 штук с одним кодом маркировки.
    При продаже одного карандаша нужно в `numerator` передать ~`1`, а в `denominator` — ~`100`.
    """  # noqa: E501

    __numerator = None
    """Числитель — количество продаваемых товаров из одной потребительской упаковки (тег в 54 ФЗ — 1293). Не может превышать `denominator`. """  # noqa: E501

    __denominator = None
    """Знаменатель — общее количество товаров в потребительской упаковке (тег в 54 ФЗ — 1294)."""  # noqa: E501

    @property
    def numerator(self):
        """
        Возвращает numerator модели MarkQuantity.

        :return: numerator модели MarkQuantity.
        :rtype: int
        """
        return self.__numerator

    @numerator.setter
    def numerator(self, value):
        """
        Устанавливает numerator модели MarkQuantity.

        :param value: numerator модели MarkQuantity.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `numerator`, must not be `None`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `numerator`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__numerator = value

    @property
    def denominator(self):
        """
        Возвращает denominator модели MarkQuantity.

        :return: denominator модели MarkQuantity.
        :rtype: int
        """
        return self.__denominator

    @denominator.setter
    def denominator(self, value):
        """
        Устанавливает denominator модели MarkQuantity.

        :param value: denominator модели MarkQuantity.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `denominator`, must not be `None`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `denominator`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__denominator = value

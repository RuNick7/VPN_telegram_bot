# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class CreditCard(BaseObject):
    """
    Данные банковской карты.
    """  # noqa: E501

    __first6 = None
    """Первые 6 цифр номера карты (BIN). При оплате картой, %[сохраненной в ЮKassa](/developers/payment-acceptance/scenario-extensions/recurring-payments) и других сервисах, переданный BIN может не соответствовать значениям `last4`, `expiry_year`, `expiry_month`."""  # noqa: E501

    __last4 = None
    """Последние 4 цифры номера карты."""  # noqa: E501

    __expiry_year = None
    """Срок действия, год, YYYY."""  # noqa: E501

    __expiry_month = None
    """Срок действия, месяц, MM."""  # noqa: E501

    __card_type = None
    """Тип банковской карты."""  # noqa: E501

    __card_product = None
    """Карточный продукт платежной системы, с которым ассоциирована банковская карта."""  # noqa: E501

    __issuer_country = None
    """
    Код страны, в которой выпущена карта.
    Передается в формате [ISO-3166 alpha-2](https://www.iso.org/obp/ui/#iso:pub:PUB500001:en).
    Пример: RU.
    """  # noqa: E501

    __issuer_name = None
    """Наименование банка, выпустившего карту."""  # noqa: E501

    __source = None
    """
     Источник данных банковской карты.
    Возможные значения: ~`apple_pay`, ~`google_pay`, ~`mir_pay`.
    Присутствует, если пользователь при оплате выбрал карту, сохраненную в Apple Pay, Google Pay или MirPay.
    """  # noqa: E501

    __id = None
    """Публичный идентификатор карты"""  # noqa: E501

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
    def card_product(self):
        """
        Возвращает card_product модели CreditCard.

        :return: card_product модели CreditCard.
        :rtype: BankCardProduct
        """
        return self.__card_product

    @card_product.setter
    def card_product(self, value):
        """
        Устанавливает card_product модели CreditCard.

        :param value: card_product модели CreditCard.
        :type value: BankCardProduct
        """
        if isinstance(value, dict):
            self.__card_product = BankCardProduct(value)
        elif isinstance(value, BankCardProduct):
            self.__card_product = value
        else:
            raise TypeError('Invalid card_product data type in CreditCard.card_product')

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

    @property
    def source(self):
        """
        Возвращает source модели CreditCard.

        :return: source модели CreditCard.
        :rtype: str
        """
        return self.__source

    @source.setter
    def source(self, value):
        """
        Устанавливает source модели CreditCard.

        :param value: source модели CreditCard.
        :type value: str
        """
        self.__source = str(value)

    @property
    def id(self):
        """
        Возвращает id модели CreditCard.

        :return: id модели CreditCard.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели CreditCard.

        :param value: id модели CreditCard.
        :type value: str
        """
        self.__id = value

class BankCardProduct(BaseObject):
    """Карточный продукт платежной системы, с которым ассоциирована банковская карта.
    Например, карточные продукты платежной системы Мир:
    `Mir Classic`, ~`Mir Classic Credit`, ~`MIR Privilege Plus` и другие. """  # noqa: E501

    __code = None
    """Код карточного продукта. Пример: ~`MCP` """  # noqa: E501

    __name = None
    """Название карточного продукта. Пример: ~`MIR Privilege` """  # noqa: E501

    @property
    def code(self):
        """Возвращает code модели BankCardProduct.

        :return: code модели BankCardProduct.
        :rtype: str
        """
        return self.__code

    @code.setter
    def code(self, value):
        """Устанавливает code модели BankCardProduct.

        :param value: code модели BankCardProduct.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `code`, must not be `None`")  # noqa: E501
        self.__code = value

    @property
    def name(self):
        """Возвращает name модели BankCardProduct.

        :return: name модели BankCardProduct.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """Устанавливает name модели BankCardProduct.

        :param value: name модели BankCardProduct.
        :type value: str
        """
        self.__name = value

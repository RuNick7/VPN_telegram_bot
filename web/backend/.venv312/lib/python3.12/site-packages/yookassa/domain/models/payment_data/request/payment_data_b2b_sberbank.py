# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataB2bSberbank(PaymentData):
    """
    Данные для оплаты через СберБанк Бизнес Онлайн.
    """  # noqa: E501

    __payment_purpose = None
    """Назначение платежа (не больше 210 символов)."""  # noqa: E501

    __vat_data = None
    """Данные об НДС."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataB2bSberbank, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.B2B_SBERBANK:
            self.type = PaymentMethodType.B2B_SBERBANK

    @property
    def payment_purpose(self):
        """
        Возвращает payment_purpose модели PaymentDataB2bSberbank.

        :return: payment_purpose модели PaymentDataB2bSberbank.
        :rtype: str
        """
        return self.__payment_purpose

    @payment_purpose.setter
    def payment_purpose(self, value):
        """
        Устанавливает payment_purpose модели PaymentDataB2bSberbank.

        :param value: payment_purpose модели PaymentDataB2bSberbank.
        :type value: str
        """
        self.__payment_purpose = str(value)

    @property
    def vat_data(self):
        """
        Возвращает vat_data модели PaymentDataB2bSberbank.

        :return: vat_data модели PaymentDataB2bSberbank.
        :rtype: VatData
        """
        return self.__vat_data

    @vat_data.setter
    def vat_data(self, value):
        """
        Устанавливает vat_data модели PaymentDataB2bSberbank.

        :param value: vat_data модели PaymentDataB2bSberbank.
        :type value: VatData
        """
        if isinstance(value, dict):
            self.__vat_data = VatData(value)
        elif isinstance(value, VatData):
            self.__vat_data = value
        else:
            raise TypeError('Invalid vat_data value type')


class VatData(BaseObject):
    """
    Данные об НДС, если товар или услуга облагается налогом (в параметре `type` передано значение ~`calculated`).
    """  # noqa: E501

    __type = None
    """Код способа расчета НДС."""  # noqa: E501

    __rate = None
    """Налоговая ставка (в процентах). Возможные значения: ~`5`, ~`7`, ~`10`, ~`20` и ~`22`.  С 1 января 2026 года ставка НДС 22% применяется вместо ставки 20%. """  # noqa: E501

    __amount = None
    """Сумма НДС."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели VatData.

        :return: type модели VatData.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели VatData.

        :param value: type модели VatData.
        :type value: str
        """
        if value in VatDataType.__dict__.values():
            self.__type = str(value)
        else:
            raise ValueError('Invalid type value')

    @property
    def rate(self):
        """
        Возвращает rate модели VatData.

        :return: rate модели VatData.
        :rtype: str
        """
        return self.__rate

    @rate.setter
    def rate(self, value):
        """
        Устанавливает rate модели VatData.

        :param value: rate модели VatData.
        :type value: str
        """
        if value in VatDataRate.__dict__.values():
            self.__rate = int(value)
        else:
            raise ValueError('Invalid rate value')

    @property
    def amount(self):
        """
        Возвращает amount модели VatData.

        :return: amount модели VatData.
        :rtype: object
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели VatData.

        :param value: amount модели VatData.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')


class VatDataType:
    """
    Тип способа расчета НДС.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    CALCULATED = 'calculated'
    """Сумма НДС включена в сумму платежа."""
    MIXED = 'mixed'
    """Разные ставки НДС для разных товаров."""
    UNTAXED = 'untaxed'
    """Сумма платежа НДС не облагается."""


class VatDataRate:
    """
    Налоговая ставка НДС.
    """   # noqa: E501

    """
    Список допустимых значений
    """
    RATE_5 = 5
    """5%."""
    RATE_7 = 7
    """7%."""
    RATE_10 = 10
    """10%."""
    RATE_18 = 18
    """18%."""
    RATE_20 = 20
    """20%."""
    RATE_22 = 22
    """22% - С 1 января 2026 года ставка НДС 22% применяется вместо ставки 20%."""

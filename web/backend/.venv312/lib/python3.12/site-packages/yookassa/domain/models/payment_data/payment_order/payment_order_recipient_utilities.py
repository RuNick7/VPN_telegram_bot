# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models.payment_data.payment_order.payment_order_recipient_bank_utilities import PaymentOrderRecipientBankUtilities


class PaymentOrderRecipientUtilities(BaseObject):
    """Получатель платежа"""  # noqa: E501

    __name = None
    """Название получателя."""  # noqa: E501

    __inn = None
    """ИНН получателя."""  # noqa: E501

    __kpp = None
    """КПП получателя."""  # noqa: E501

    __bank = None
    """Банк получателя.""" # noqa: E501

    @property
    def name(self):
        """Возвращает name модели PaymentOrderRecipient.

        :return: name модели PaymentOrderRecipient.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """Устанавливает name модели PaymentOrderRecipient.

        :param value: name модели PaymentOrderRecipient.
        :type value: str
        """
        self.__name = value

    @property
    def inn(self):
        """Возвращает inn модели PaymentOrderRecipient.

        :return: inn модели PaymentOrderRecipient.
        :rtype: str
        """
        return self.__inn

    @inn.setter
    def inn(self, value):
        """Устанавливает inn модели PaymentOrderRecipient.

        :param value: inn модели PaymentOrderRecipient.
        :type value: str
        """
        if value is not None and not re.search(r'^[0-9]{10}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `inn`, must be a follow pattern or equal to `/[0-9]{10}/`")  # noqa: E501
        self.__inn = value

    @property
    def kpp(self):
        """Возвращает kpp модели PaymentOrderRecipient.

        :return: kpp модели PaymentOrderRecipient.
        :rtype: str
        """
        return self.__kpp

    @kpp.setter
    def kpp(self, value):
        """Устанавливает kpp модели PaymentOrderRecipient.

        :param value: kpp модели PaymentOrderRecipient.
        :type value: str
        """
        if value is not None and not re.search(r'^[0-9]{9}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `kpp`, must be a follow pattern or equal to `/[0-9]{9}/`")  # noqa: E501
        self.__kpp = value

    @property
    def bank(self):
        """Возвращает bank модели PaymentOrderRecipient.

        :return: bank модели PaymentOrderRecipient.
        :rtype: PaymentOrderRecipientBankUtilities
        """
        return self.__bank

    @bank.setter
    def bank(self, value):
        """Устанавливает bank модели PaymentOrderRecipient.

        :param value: bank модели PaymentOrderRecipient.
        :type value: PaymentOrderRecipientBankUtilities
        """
        if isinstance(value, dict):
            self.__bank = PaymentOrderRecipientBankUtilities(value)
        elif isinstance(value, PaymentOrderRecipientBankUtilities):
            self.__bank = value
        else:
            raise TypeError('Invalid bank type in PaymentOrderRecipient.bank')



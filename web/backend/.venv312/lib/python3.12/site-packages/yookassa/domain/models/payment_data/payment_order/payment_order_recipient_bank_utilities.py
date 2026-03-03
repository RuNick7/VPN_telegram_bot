# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PaymentOrderRecipientBankUtilities(BaseObject):

    __name = None
    """Название банка получателя. Максимум 45 символов."""  # noqa: E501

    __bic = None
    """БИК банка получателя."""  # noqa: E501

    __account = None
    """Счет получателя в банке."""  # noqa: E501

    __correspondent_account = None
    """Корреспондентский счет банка получателя."""  # noqa: E501

    @property
    def name(self):
        """Возвращает name модели PaymentOrderRecipientBank.

        :return: name модели PaymentOrderRecipientBank.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """Устанавливает name модели PaymentOrderRecipientBank.

        :param value: name модели PaymentOrderRecipientBank.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 45:
            raise ValueError("Invalid value for `name`, length must be less than or equal to `45`")  # noqa: E501
        self.__name = value

    @property
    def bic(self):
        """Возвращает bic модели PaymentOrderRecipientBank.

        :return: bic модели PaymentOrderRecipientBank.
        :rtype: str
        """
        return self.__bic

    @bic.setter
    def bic(self, value):
        """Устанавливает bic модели PaymentOrderRecipientBank.

        :param value: bic модели PaymentOrderRecipientBank.
        :type value: str
        """
        if value is not None and not re.search(r'^[0-9]{9}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `bic`, must be a follow pattern or equal to `/[0-9]{9}/`")  # noqa: E501
        self.__bic = value

    @property
    def account(self):
        """Возвращает account модели PaymentOrderRecipientBank.

        :return: account модели PaymentOrderRecipientBank.
        :rtype: str
        """
        return self.__account

    @account.setter
    def account(self, value):
        """Устанавливает account модели PaymentOrderRecipientBank.

        :param value: account модели PaymentOrderRecipientBank.
        :type value: str
        """
        self.__account = value

    @property
    def correspondent_account(self):
        """Возвращает correspondent_account модели PaymentOrderRecipientBank.

        :return: correspondent_account модели PaymentOrderRecipientBank.
        :rtype: str
        """
        return self.__correspondent_account

    @correspondent_account.setter
    def correspondent_account(self, value):
        """Устанавливает correspondent_account модели PaymentOrderRecipientBank.

        :param value: correspondent_account модели PaymentOrderRecipientBank.
        :type value: str
        """
        self.__correspondent_account = value



# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class MerchantCustomerBankAccount(BaseObject):
    """
    Данные банковского счета, открытого в вашей системе. Необходимо передавать, если пользователь %[пополняет свой счет](/developers/payment-acceptance/scenario-extensions/bank-account-in-merchant-system).
    """  # noqa: E501

    __account_number = None
    """Номер банковского счета. Формат — 20 символов."""  # noqa: E501

    __bic = None
    """Банковский идентификационный код (БИК) банка, в котором открыт счет."""  # noqa: E501

    @property
    def account_number(self):
        """
        Возвращает account_number модели MerchantCustomerBankAccount.

        :return: account_number модели MerchantCustomerBankAccount.
        :rtype: str
        """
        return self.__account_number

    @account_number.setter
    def account_number(self, value):
        """
        Устанавливает account_number модели MerchantCustomerBankAccount.

        :param value: account_number модели MerchantCustomerBankAccount.
        :type value: str
        """
        if value is not None and not re.search(r'^[0-9]{20}$', value):  # noqa: E501
            raise ValueError("Invalid value for `account_number`, must be a follow pattern or equal to `/[0-9]{20}/`")  # noqa: E501
        self.__account_number = value

    @property
    def bic(self):
        """
        Возвращает bic модели MerchantCustomerBankAccount.

        :return: bic модели MerchantCustomerBankAccount.
        :rtype: str
        """
        return self.__bic

    @bic.setter
    def bic(self, value):
        """
        Устанавливает bic модели MerchantCustomerBankAccount.

        :param value: bic модели MerchantCustomerBankAccount.
        :type value: str
        """
        if value is not None and not re.search(r'^\d{9}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `bic`, must be a follow pattern or equal to `/\d{9}/`")  # noqa: E501
        self.__bic = value

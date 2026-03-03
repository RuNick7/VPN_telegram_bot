# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models.payment_data.request.merchant_customer_bank_account import MerchantCustomerBankAccount


class FraudData(BaseObject):
    """
    Информация для проверки операции на мошенничество.
    """  # noqa: E501

    __topped_up_phone = None
    """Номер телефона для пополнения. Не более 15 символов. Пример: ~`79110000000`.<br/> Необходим при %[пополнении баланса телефона](/developers/payment-acceptance/scenario-extensions/top-up-phones-balance). """  # noqa: E501

    __merchant_customer_bank_account = None
    """Данные банковского счета, открытого в вашей системе."""  # noqa: E501

    @property
    def topped_up_phone(self):
        """
        Возвращает topped_up_phone модели FraudData.

        :return: topped_up_phone модели FraudData.
        :rtype: str
        """
        return self.__topped_up_phone

    @topped_up_phone.setter
    def topped_up_phone(self, value):
        """
        Устанавливает topped_up_phone модели FraudData.

        :param value: topped_up_phone модели FraudData.
        :type value: str
        """
        if value is not None and not re.search(r'^[0-9]{4,15}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `topped_up_phone`, must be a follow pattern or equal to `/[0-9]{4,15}/`")  # noqa: E501
        self.__topped_up_phone = value

    @property
    def merchant_customer_bank_account(self):
        """
        Возвращает merchant_customer_bank_account модели FraudData.

        :return: merchant_customer_bank_account модели FraudData.
        :rtype: MerchantCustomerBankAccount
        """
        return self.__merchant_customer_bank_account

    @merchant_customer_bank_account.setter
    def merchant_customer_bank_account(self, value):
        """
        Устанавливает merchant_customer_bank_account модели FraudData.

        :param value: merchant_customer_bank_account модели FraudData.
        :type value: MerchantCustomerBankAccount
        """
        if isinstance(value, dict):
            self.__merchant_customer_bank_account = MerchantCustomerBankAccount(value)
        elif isinstance(value, MerchantCustomerBankAccount):
            self.__merchant_customer_bank_account = value
        else:
            raise TypeError('Invalid merchant_customer_bank_account data type in FraudData.merchant_customer_bank_account')  # noqa: E501

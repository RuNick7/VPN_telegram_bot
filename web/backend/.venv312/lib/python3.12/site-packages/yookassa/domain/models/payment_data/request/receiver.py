# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class Receiver(BaseObject):
    """Реквизиты получателя оплаты при %[пополнении электронного кошелька, банковского счета или баланса телефона](/developers/payment-acceptance/scenario-extensions/receiver-data)."""  # noqa: E501

    __type = None
    """Код получателя оплаты."""

    @property
    def type(self):
        """Возвращает type модели ReceiverBankAccount.

        :return: type модели ReceiverBankAccount.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели ReceiverBankAccount.

        :param value: type модели ReceiverBankAccount.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = value


class ReceiverBankAccount(Receiver):
    """Реквизиты для пополнения банковского счета."""  # noqa: E501

    __account_number = None
    """Номер банковского счета. Формат — 20 символов."""  # noqa: E501

    __bic = None
    """Банковский идентификационный код (БИК) банка, в котором открыт счет. Формат — 9 символов."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ReceiverBankAccount, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ReceiverType.BANK_ACCOUNT:
            self.type = ReceiverType.BANK_ACCOUNT

    @property
    def account_number(self):
        """Возвращает account_number модели ReceiverBankAccount.

        :return: account_number модели ReceiverBankAccount.
        :rtype: str
        """
        return self.__account_number

    @account_number.setter
    def account_number(self, value):
        """Устанавливает account_number модели ReceiverBankAccount.

        :param value: account_number модели ReceiverBankAccount.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `account_number`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 20:
            raise ValueError("Invalid value for `account_number`, length must be less than or equal to `20`")  # noqa: E501
        if value is not None and not re.search(r'^\d{20}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `account_number`, must be a follow pattern or equal to `/\d{20}/`")  # noqa: E501
        self.__account_number = value

    @property
    def bic(self):
        """Возвращает bic модели ReceiverBankAccount.

        :return: bic модели ReceiverBankAccount.
        :rtype: str
        """
        return self.__bic

    @bic.setter
    def bic(self, value):
        """Устанавливает bic модели ReceiverBankAccount.

        :param value: bic модели ReceiverBankAccount.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `bic`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 9:
            raise ValueError("Invalid value for `bic`, length must be less than or equal to `9`")  # noqa: E501
        if value is not None and not re.search(r'^\d{9}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `bic`, must be a follow pattern or equal to `/\d{9}/`")  # noqa: E501
        self.__bic = value


class ReceiverDigitalWallet(BaseObject):
    """Реквизиты для пополнения баланса электронного кошелька."""  # noqa: E501

    __type = None
    """Код получателя оплаты."""  # noqa: E501

    __account_number = None
    """Идентификатор электронного кошелька для пополнения. Максимум 20 символов."""  # noqa: E501

    @property
    def type(self):
        """Возвращает type модели ReceiverDigitalWallet.

        :return: type модели ReceiverDigitalWallet.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели ReceiverDigitalWallet.

        :param value: type модели ReceiverDigitalWallet.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = value

    @property
    def account_number(self):
        """Возвращает account_number модели ReceiverDigitalWallet.

        :return: account_number модели ReceiverDigitalWallet.
        :rtype: str
        """
        return self.__account_number

    @account_number.setter
    def account_number(self, value):
        """Устанавливает account_number модели ReceiverDigitalWallet.

        :param value: account_number модели ReceiverDigitalWallet.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `account_number`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 20:
            raise ValueError("Invalid value for `account_number`, length must be less than or equal to `20`")  # noqa: E501
        self.__account_number = value


class ReceiverMobileBalance(BaseObject):
    """Реквизиты для пополнения баланса телефона."""  # noqa: E501

    __type = None
    """Код получателя оплаты."""  # noqa: E501

    __phone = None

    @property
    def type(self):
        """Возвращает type модели ReceiverMobileBalance.

        :return: type модели ReceiverMobileBalance.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели ReceiverMobileBalance.

        :param value: type модели ReceiverMobileBalance.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = value

    @property
    def phone(self):
        """Возвращает phone модели ReceiverMobileBalance.

        :return: phone модели ReceiverMobileBalance.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """Устанавливает phone модели ReceiverMobileBalance.

        :param value: phone модели ReceiverMobileBalance.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `phone`, must not be `None`")  # noqa: E501
        self.__phone = value


class ReceiverType:
    """Код получателя оплаты."""  # noqa: E501

    """
    Список допустимых значений
    """
    BANK_ACCOUNT = "bank_account"
    DIGITAL_WALLET = "digital_wallet"
    MOBILE_BALANCE = "mobile_balance"


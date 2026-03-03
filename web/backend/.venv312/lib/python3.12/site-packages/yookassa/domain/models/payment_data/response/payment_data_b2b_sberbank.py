# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData
from yookassa.domain.models.payment_data.request.payment_data_b2b_sberbank import VatData


class PaymentDataB2bSberbank(ResponsePaymentData):
    """
    Оплата через Сбербанк Бизнес Онлайн.
    """  # noqa: E501

    __payment_purpose = None
    """Назначение платежа (не больше 210 символов)."""  # noqa: E501

    __vat_data = None
    """Данные об НДС."""  # noqa: E501

    __payer_bank_details = None
    """Банковские реквизиты плательщика."""  # noqa: E501

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
            raise TypeError('Invalid vat_data value type in PaymentDataB2bSberbank')

    @property
    def payer_bank_details(self):
        """
        Возвращает payer_bank_details модели PaymentDataB2bSberbank.

        :return: payer_bank_details модели PaymentDataB2bSberbank.
        :rtype: PayerBankDetails
        """
        return self.__payer_bank_details

    @payer_bank_details.setter
    def payer_bank_details(self, value):
        """
        Устанавливает payer_bank_details модели PaymentDataB2bSberbank.

        :param value: payer_bank_details модели PaymentDataB2bSberbank.
        :type value: PayerBankDetails
        """
        if isinstance(value, dict):
            self.__payer_bank_details = PayerBankDetails(value)
        elif isinstance(value, PayerBankDetails):
            self.__payer_bank_details = value
        else:
            raise TypeError('Invalid payer_bank_details value type in PaymentDataB2bSberbank')


class PayerBankDetails(BaseObject):
    """
    Банковские реквизиты плательщика (юридического лица или ИП).
    """  # noqa: E501

    __full_name = None
    """Полное наименование организации."""  # noqa: E501

    __short_name = None
    """Сокращенное наименование организации."""  # noqa: E501

    __address = None
    """Адрес организации."""  # noqa: E501

    __inn = None
    """Индивидуальный налоговый номер (ИНН) организации."""  # noqa: E501

    __kpp = None
    """Код причины постановки на учет (КПП) организации."""  # noqa: E501

    __bank_name = None
    """Наименование банка организации."""  # noqa: E501

    __bank_branch = None
    """Отделение банка организации."""  # noqa: E501

    __bank_bik = None
    """Банковский идентификационный код (БИК) банка организации."""  # noqa: E501

    __account = None
    """Номер счета организации."""  # noqa: E501

    @property
    def full_name(self):
        """
        Возвращает full_name модели PayerBankDetails.

        :return: full_name модели PayerBankDetails.
        :rtype: str
        """
        return self.__full_name

    @full_name.setter
    def full_name(self, value):
        """
        Устанавливает full_name модели PayerBankDetails.

        :param value: full_name модели PayerBankDetails.
        :type value: str
        """
        self.__full_name = str(value)

    @property
    def short_name(self):
        """
        Возвращает short_name модели PayerBankDetails.

        :return: short_name модели PayerBankDetails.
        :rtype: str
        """
        return self.__short_name

    @short_name.setter
    def short_name(self, value):
        """
        Устанавливает short_name модели PayerBankDetails.

        :param value: short_name модели PayerBankDetails.
        :type value: str
        """
        self.__short_name = str(value)

    @property
    def address(self):
        """
        Возвращает address модели PayerBankDetails.

        :return: address модели PayerBankDetails.
        :rtype: str
        """
        return self.__address

    @address.setter
    def address(self, value):
        """
        Устанавливает address модели PayerBankDetails.

        :param value: address модели PayerBankDetails.
        :type value: str
        """
        self.__address = str(value)

    @property
    def inn(self):
        """
        Возвращает inn модели PayerBankDetails.

        :return: inn модели PayerBankDetails.
        :rtype: str
        """
        return self.__inn

    @inn.setter
    def inn(self, value):
        """
        Устанавливает inn модели PayerBankDetails.

        :param value: inn модели PayerBankDetails.
        :type value: str
        """
        self.__inn = str(value)

    @property
    def kpp(self):
        """
        Возвращает kpp модели PayerBankDetails.

        :return: kpp модели PayerBankDetails.
        :rtype: str
        """
        return self.__inn

    @kpp.setter
    def kpp(self, value):
        """
        Устанавливает kpp модели PayerBankDetails.

        :param value: kpp модели PayerBankDetails.
        :type value: str
        """
        self.__inn = str(value)

    @property
    def bank_name(self):
        """
        Возвращает bank_name модели PayerBankDetails.

        :return: bank_name модели PayerBankDetails.
        :rtype: str
        """
        return self.__bank_name

    @bank_name.setter
    def bank_name(self, value):
        """
        Устанавливает bank_name модели PayerBankDetails.

        :param value: bank_name модели PayerBankDetails.
        :type value: str
        """
        self.__bank_name = str(value)

    @property
    def bank_branch(self):
        """
        Возвращает bank_branch модели PayerBankDetails.

        :return: bank_branch модели PayerBankDetails.
        :rtype: str
        """
        return self.__bank_branch

    @bank_branch.setter
    def bank_branch(self, value):
        """
        Устанавливает bank_branch модели PayerBankDetails.

        :param value: bank_branch модели PayerBankDetails.
        :type value: str
        """
        self.__bank_branch = str(value)

    @property
    def bank_bik(self):
        """
        Возвращает bank_bik модели PayerBankDetails.

        :return: bank_bik модели PayerBankDetails.
        :rtype: str
        """
        return self.__bank_bik

    @bank_bik.setter
    def bank_bik(self, value):
        """
        Устанавливает bank_bik модели PayerBankDetails.

        :param value: bank_bik модели PayerBankDetails.
        :type value: str
        """
        self.__bank_bik = str(value)

    @property
    def account(self):
        """
        Возвращает account модели PayerBankDetails.

        :return: account модели PayerBankDetails.
        :rtype: str
        """
        return self.__account

    @account.setter
    def account(self, value):
        """
        Устанавливает account модели PayerBankDetails.

        :param value: account модели PayerBankDetails.
        :type value: str
        """
        self.__account = str(value)

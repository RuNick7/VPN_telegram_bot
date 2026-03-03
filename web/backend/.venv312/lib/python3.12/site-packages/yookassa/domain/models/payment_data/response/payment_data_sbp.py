# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData


class PaymentDataSbp(ResponsePaymentData):
    """
    Оплата через СБП (Система быстрых платежей ЦБ РФ).
    """  # noqa: E501

    __sbp_operation_id = None
    """Идентификатор операции в СБП (НСПК). Пример: ~`1027088AE4CB48CB81287833347A8777`. Обязательный параметр для платежей в статусе ~`succeeded`. В остальных случаях может отсутствовать. """  # noqa: E501

    __payer_bank_details = None
    """Реквизиты счета, который использовался для оплаты. Обязательный параметр для платежей в статусе ~`succeeded`. В остальных случаях может отсутствовать."""

    def __init__(self, *args, **kwargs):
        super(PaymentDataSbp, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBP:
            self.type = PaymentMethodType.SBP

    @property
    def sbp_operation_id(self):
        """Возвращает sbp_operation_id модели PaymentDataSbp.

        :return: sbp_operation_id модели PaymentDataSbp.
        :rtype: str
        """
        return self.__sbp_operation_id

    @sbp_operation_id.setter
    def sbp_operation_id(self, value):
        """Устанавливает sbp_operation_id модели PaymentDataSbp.

        :param value: sbp_operation_id модели PaymentDataSbp.
        :type value: str
        """
        self.__sbp_operation_id = value

    @property
    def payer_bank_details(self):
        """Возвращает payer_bank_details модели PaymentDataSbp.

        :return: payer_bank_details модели PaymentDataSbp.
        :rtype: SbpPayerBankDetails
        """
        return self.__payer_bank_details

    @payer_bank_details.setter
    def payer_bank_details(self, value):
        """Устанавливает payer_bank_details модели PaymentDataSbp.

        :param value: payer_bank_details модели PaymentDataSbp.
        :type value: SbpPayerBankDetails
        """
        if isinstance(value, dict):
            self.__payer_bank_details = SbpPayerBankDetails(value)
        elif isinstance(value, SbpPayerBankDetails):
            self.__payer_bank_details = value


class SbpPayerBankDetails(BaseObject):
    """Реквизиты счета, который использовался для оплаты.  Обязательный параметр для платежей в статусе ~`succeeded`. В остальных случаях может отсутствовать. """  # noqa: E501

    __bank_id = None
    """Идентификатор банка или платежного сервиса в СБП (НСПК)."""  # noqa: E501

    __bic = None

    @property
    def bank_id(self):
        """Возвращает bank_id модели SbpPayerBankDetails.

        :return: bank_id модели SbpPayerBankDetails.
        :rtype: str
        """
        return self.__bank_id

    @bank_id.setter
    def bank_id(self, value):
        """Устанавливает bank_id модели SbpPayerBankDetails.

        :param value: bank_id модели SbpPayerBankDetails.
        :type value: str
        """
        self.__bank_id = value

    @property
    def bic(self):
        """Возвращает bic модели SbpPayerBankDetails.

        :return: bic модели SbpPayerBankDetails.
        :rtype: str
        """
        return self.__bic

    @bic.setter
    def bic(self, value):
        """Устанавливает bic модели SbpPayerBankDetails.

        :param value: bic модели SbpPayerBankDetails.
        :type value: str
        """
        self.__bic = value

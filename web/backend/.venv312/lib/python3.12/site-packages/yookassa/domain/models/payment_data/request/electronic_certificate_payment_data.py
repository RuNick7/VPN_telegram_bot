# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class ElectronicCertificatePaymentData(BaseObject):
    """Данные от ФЭС НСПК для оплаты по электронному сертификату.  Неоходимо передавать только при [оплате со сбором данных на вашей стороне](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form). """  # noqa: E501

    __amount = None

    __basket_id = None

    @property
    def amount(self):
        """Возвращает amount модели ElectronicCertificatePaymentData.

        :return: amount модели ElectronicCertificatePaymentData.
        :rtype: ElectronicCertificatePaymentDataAmount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """Устанавливает amount модели ElectronicCertificatePaymentData.

        :param value: amount модели ElectronicCertificatePaymentData.
        :type value: ElectronicCertificatePaymentDataAmount
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `amount`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount data type in ElectronicCertificatePaymentData.amount')

    @property
    def basket_id(self):
        """Возвращает basket_id модели ElectronicCertificatePaymentData.

        :return: basket_id модели ElectronicCertificatePaymentData.
        :rtype: str
        """
        return self.__basket_id

    @basket_id.setter
    def basket_id(self, value):
        """Устанавливает basket_id модели ElectronicCertificatePaymentData.

        :param value: basket_id модели ElectronicCertificatePaymentData.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `basket_id`, must not be `None`")  # noqa: E501
        self.__basket_id = value



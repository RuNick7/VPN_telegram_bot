# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class ElectronicCertificateRefundDataRequest(BaseObject):
    """Данные от ФЭС НСПК для возврата на электронный сертификат.  Неоходимо передавать только при [оплате со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form). """  # noqa: E501

    __amount = None
    """
    Сумма, которая вернется на электронный сертификат, — значение `totalCertAmount`, которое вы получили в ФЭС НСПК в [запросе на предварительное одобрение возврата (Refund Pre-Auth)](https://www.nspk.ru/developer/api-fes#tag/Protokol-FES-NSPK-v1/operation/preAuthReturn).
    Сумма должна быть не больше общей суммы платежа (`amount`).
    """  # noqa: E501

    __basket_id = None
    """Идентификатор корзины возврата, сформированной в НСПК, — значение `returnBasketId`, которое вы получили в ФЭС НСПК в [запросе на предварительное одобрение возврата (Refund Pre-Auth)](https://www.nspk.ru/developer/api-fes#tag/Protokol-FES-NSPK-v1/operation/preAuthReturn)."""  # noqa: E501

    @property
    def amount(self):
        """Возвращает amount модели ElectronicCertificateRefundDataRequest.

        :return: amount модели ElectronicCertificateRefundDataRequest.
        :rtype: ElectronicCertificateRefundDataRequestAmount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """Устанавливает amount модели ElectronicCertificateRefundDataRequest.

        :param value: amount модели ElectronicCertificateRefundDataRequest.
        :type value: ElectronicCertificateRefundDataRequestAmount
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `amount`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount data type in ElectronicCertificateRefundDataRequest.amount')

    @property
    def basket_id(self):
        """Возвращает basket_id модели ElectronicCertificateRefundDataRequest.

        :return: basket_id модели ElectronicCertificateRefundDataRequest.
        :rtype: str
        """
        return self.__basket_id

    @basket_id.setter
    def basket_id(self, value):
        """Устанавливает basket_id модели ElectronicCertificateRefundDataRequest.

        :param value: basket_id модели ElectronicCertificateRefundDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `basket_id`, must not be `None`")  # noqa: E501
        self.__basket_id = value

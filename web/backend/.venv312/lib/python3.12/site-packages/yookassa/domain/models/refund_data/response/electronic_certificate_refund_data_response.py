# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class ElectronicCertificateRefundDataResponse(BaseObject):
    """Данные от ФЭС НСПК для возврата на электронный сертификат. """  # noqa: E501

    __basket_id = None
    """Идентификатор корзины возврата, сформированной в НСПК, — значение `returnBasketId`, которое вы получили в ФЭС НСПК в [запросе на предварительное одобрение возврата (Refund Pre-Auth)](https://www.nspk.ru/developer/api-fes#tag/Protokol-FES-NSPK-v1/operation/preAuthReturn)."""  # noqa: E501

    __amount = None
    """
    Сумма, которая вернется на электронный сертификат, — значение `totalCertAmount`, которое вы получили в ФЭС НСПК в [запросе на предварительное одобрение возврата (Refund Pre-Auth)](https://www.nspk.ru/developer/api-fes#tag/Protokol-FES-NSPK-v1/operation/preAuthReturn).
    Сумма должна быть не больше общей суммы платежа (`amount`).
    """  # noqa: E501

    @property
    def basket_id(self):
        """Возвращает basket_id модели ElectronicCertificateRefundDataResponse.

        :return: basket_id модели ElectronicCertificateRefundDataResponse.
        :rtype: str
        """
        return self.__basket_id

    @basket_id.setter
    def basket_id(self, value):
        """Устанавливает basket_id модели ElectronicCertificateRefundDataResponse.

        :param value: basket_id модели ElectronicCertificateRefundDataResponse.
        :type value: str
        """
        self.__basket_id = value

    @property
    def amount(self):
        """Возвращает amount модели ElectronicCertificateRefundDataResponse.

        :return: amount модели ElectronicCertificateRefundDataResponse.
        :rtype: ElectronicCertificateRefundDataResponseAmount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """Устанавливает amount модели ElectronicCertificateRefundDataResponse.

        :param value: amount модели ElectronicCertificateRefundDataResponse.
        :type value: ElectronicCertificateRefundDataResponseAmount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount data type in ElectronicCertificateRefundDataResponse.amount')

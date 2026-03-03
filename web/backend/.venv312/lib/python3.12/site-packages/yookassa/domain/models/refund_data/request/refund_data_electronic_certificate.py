# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.refund_data.electronic_certificate_refund_article import ElectronicCertificateRefundArticle
from yookassa.domain.models.refund_data.refund_data import RequestRefundData
from yookassa.domain.models.refund_data.request.electronic_certificate_refund_data_request import \
    ElectronicCertificateRefundDataRequest


class RefundDataElectronicCertificate(RequestRefundData):
    """
    Данные для возврата платежа через СБП (НСПК).
    """  # noqa: E501

    __electronic_certificate = None
    """Данные от ФЭС НСПК для возврата на электронный сертификат."""

    __articles = None
    """Корзина возврата — список возвращаемых товаров, для оплаты которых использовался электронный сертификат.  Присутствует, если оплата была на [готовой странице ЮKassa](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form). """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(RefundDataElectronicCertificate, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.ELECTRONIC_CERTIFICATE:
            self.type = PaymentMethodType.ELECTRONIC_CERTIFICATE

    @property
    def electronic_certificate(self):
        """Возвращает electronic_certificate модели RefundDataElectronicCertificate.

        :return: electronic_certificate модели RefundDataElectronicCertificate.
        :rtype: ElectronicCertificateRefundDataResponse
        """
        return self.__electronic_certificate

    @electronic_certificate.setter
    def electronic_certificate(self, value):
        """Устанавливает electronic_certificate модели RefundDataElectronicCertificate.

        :param value: electronic_certificate модели RefundDataElectronicCertificate.
        :type value: ElectronicCertificateRefundDataResponse
        """
        if isinstance(value, dict):
            self.__electronic_certificate = ElectronicCertificateRefundDataRequest(value)
        elif isinstance(value, ElectronicCertificateRefundDataRequest):
            self.__electronic_certificate = value
        else:
            raise TypeError('Invalid electronic_certificate data type in RefundDataElectronicCertificate.electronic_certificate')

    @property
    def articles(self):
        """Возвращает articles модели RefundDataElectronicCertificate.

        :return: articles модели RefundDataElectronicCertificate.
        :rtype: list[ElectronicCertificateRefundArticle]
        """
        return self.__articles

    @articles.setter
    def articles(self, value):
        """Устанавливает articles модели RefundDataElectronicCertificate.

        :param value: articles модели RefundDataElectronicCertificate.
        :type value: list[ElectronicCertificateRefundArticle]
        """
        if isinstance(value, list):
            articles_array = []
            for articlesData in value:
                if isinstance(articlesData, dict):
                    articles_array.append(ElectronicCertificateRefundArticle(articlesData))
                elif isinstance(articlesData, ElectronicCertificateRefundArticle):
                    articles_array.append(articlesData)
                else:
                    raise TypeError('Invalid articles data type in RefundDataElectronicCertificate.articles')

            self.__articles = articles_array
        else:
            raise TypeError('Invalid articles value type in RefundDataElectronicCertificate')


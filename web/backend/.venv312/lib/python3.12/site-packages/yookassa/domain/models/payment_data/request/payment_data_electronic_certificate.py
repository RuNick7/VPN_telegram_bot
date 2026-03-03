# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import PaymentMethodType
from yookassa.domain.models.payment_data.electronic_certificate.electronic_certificate_article import \
    ElectronicCertificateArticle
from yookassa.domain.models.payment_data.request.electronic_certificate_payment_data import \
    ElectronicCertificatePaymentData
from yookassa.domain.models.payment_data.request.payment_data_bank_card import PaymentDataBankCard


class PaymentDataElectronicCertificate(PaymentDataBankCard):
    """Данные для оплаты по электронному сертификату."""  # noqa: E501

    __electronic_certificate = None

    __articles = None
    """Корзина покупки (в терминах НСПК) — список товаров, которые можно оплатить по сертификату.  Необходимо передавать только при [оплате на готовой странице ЮKassa](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form). """  # noqa: E501


    def __init__(self, *args, **kwargs):
        super(PaymentDataElectronicCertificate, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.ELECTRONIC_CERTIFICATE:
            self.type = PaymentMethodType.ELECTRONIC_CERTIFICATE

    @property
    def electronic_certificate(self):
        """Возвращает electronic_certificate модели PaymentMethodDataElectronicCertificate.

        :return: electronic_certificate модели PaymentMethodDataElectronicCertificate.
        :rtype: ElectronicCertificatePaymentData
        """
        return self.__electronic_certificate

    @electronic_certificate.setter
    def electronic_certificate(self, value):
        """Устанавливает electronic_certificate модели PaymentMethodDataElectronicCertificate.

        :param value: electronic_certificate модели PaymentMethodDataElectronicCertificate.
        :type value: ElectronicCertificatePaymentData
        """
        if isinstance(value, dict):
            self.__electronic_certificate = ElectronicCertificatePaymentData(value)
        elif isinstance(value, ElectronicCertificatePaymentData):
            self.__electronic_certificate = value
        else:
            raise TypeError('Invalid electronic_certificate data type in PaymentMethodDataElectronicCertificate.electronic_certificate')

    @property
    def articles(self):
        """Возвращает articles модели PaymentMethodDataElectronicCertificate.

        :return: articles модели PaymentMethodDataElectronicCertificate.
        :rtype: list[ElectronicCertificateArticle]
        """
        return self.__articles

    @articles.setter
    def articles(self, value):
        """Устанавливает articles модели PaymentMethodDataElectronicCertificate.

        :param value: articles модели PaymentMethodDataElectronicCertificate.
        :type value: list[ElectronicCertificateArticle]
        """
        if isinstance(value, list):
            articles_array = []
            for articlesData in value:
                if isinstance(articlesData, dict):
                    articles_array.append(ElectronicCertificateArticle(articlesData))
                elif isinstance(articlesData, ElectronicCertificateArticle):
                    articles_array.append(articlesData)
                else:
                    raise TypeError('Invalid articles data type in PaymentMethodDataElectronicCertificate.articles')

            self.__articles = articles_array
        else:
            raise TypeError('Invalid articles value type in PaymentMethodDataElectronicCertificate')



# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import PaymentMethodType
from yookassa.domain.models.payment_data.electronic_certificate.electronic_certificate import ElectronicCertificate
from yookassa.domain.models.payment_data.electronic_certificate.electronic_certificate_approved_payment_article import \
    ElectronicCertificateApprovedPaymentArticle
from yookassa.domain.models.payment_data.response.payment_data_bank_card import PaymentDataBankCard


class PaymentDataElectronicCertificate(PaymentDataBankCard):
    """Оплата по электронному сертификату."""  # noqa: E501

    __electronic_certificate = None
    """Данные от ФЭС НСПК для оплаты по электронному сертификату. """  # noqa: E501

    __articles = None
    """Одобренная корзина покупки — список товаров, одобренных к оплате по электронному сертификату.  Присутствует только при [оплате на готовой странице ЮKassa](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form). """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataBankCard, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.ELECTRONIC_CERTIFICATE:
            self.type = PaymentMethodType.ELECTRONIC_CERTIFICATE

    @property
    def electronic_certificate(self):
        """Возвращает electronic_certificate модели PaymentMethodElectronicCertificate.

        :return: electronic_certificate модели PaymentMethodElectronicCertificate.
        :rtype: object
        """
        return self.__electronic_certificate

    @electronic_certificate.setter
    def electronic_certificate(self, value):
        """Устанавливает electronic_certificate модели PaymentMethodElectronicCertificate.

        :param value: electronic_certificate модели PaymentMethodElectronicCertificate.
        :type value: object
        """
        if isinstance(value, dict):
            self.__electronic_certificate = ElectronicCertificate(value)
        elif isinstance(value, ElectronicCertificate):
            self.__electronic_certificate = value
        else:
            raise TypeError(
                'Invalid electronic_certificate data type in PaymentDataElectronicCertificate.electronic_certificate')

    @property
    def articles(self):
        """Возвращает articles модели PaymentMethodElectronicCertificate.

        :return: articles модели PaymentMethodElectronicCertificate.
        :rtype: list[ElectronicCertificateApprovedPaymentArticle]
        """
        return self.__articles

    @articles.setter
    def articles(self, value):
        """Устанавливает articles модели PaymentMethodElectronicCertificate.

        :param value: articles модели PaymentMethodElectronicCertificate.
        :type value: list[ElectronicCertificateApprovedPaymentArticle]
        """
        if isinstance(value, list):
            articles_array = []
            for articlesData in value:
                if isinstance(articlesData, dict):
                    articles_array.append(ElectronicCertificateApprovedPaymentArticle(articlesData))
                elif isinstance(articlesData, ElectronicCertificateApprovedPaymentArticle):
                    articles_array.append(articlesData)
                else:
                    raise TypeError('Invalid articles data type in PaymentDataElectronicCertificate.articles')

            self.__articles = articles_array
        else:
            raise TypeError('Invalid articles value type in PaymentDataElectronicCertificate')



# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models.payment_data.electronic_certificate.electronic_certificate import ElectronicCertificate


class ElectronicCertificateApprovedPaymentArticle(BaseObject):
    """Товарная позиция в одобренной корзине покупки при оплате по электронному сертификату."""  # noqa: E501

    __article_number = None
    """Порядковый номер товара в корзине. От 1 до 999 включительно. """  # noqa: E501

    __tru_code = None
    """Код ТРУ. 30 символов, две группы цифр, разделенные точкой. Формат: ~`NNNNNNNNN.NNNNNNNNNYYYYMMMMZZZ`, где ~`NNNNNNNNN.NNNNNNNNN` — код вида ТРУ по [Перечню ТРУ](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1), ~`YYYY` — код производителя, ~`MMMM` — код модели, ~`ZZZ` — код страны производителя. Пример: ~`329921120.06001010200080001643`  [Как сформировать код ТРУ](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payments-preparations-tru-code) """  # noqa: E501

    __article_code = None
    """Код товара в вашей системе. Максимум 128 символов. """  # noqa: E501

    __certificates = None
    """Список электронных сертификатов, которые используются для оплаты покупки."""  # noqa: E501

    @property
    def article_number(self):
        """Возвращает article_number модели ElectronicCertificateApprovedPaymentArticle.

        :return: article_number модели ElectronicCertificateApprovedPaymentArticle.
        :rtype: int
        """
        return self.__article_number

    @article_number.setter
    def article_number(self, value):
        """Устанавливает article_number модели ElectronicCertificateApprovedPaymentArticle.

        :param value: article_number модели ElectronicCertificateApprovedPaymentArticle.
        :type value: int
        """
        self.__article_number = value

    @property
    def tru_code(self):
        """Возвращает tru_code модели ElectronicCertificateApprovedPaymentArticle.

        :return: tru_code модели ElectronicCertificateApprovedPaymentArticle.
        :rtype: str
        """
        return self.__tru_code

    @tru_code.setter
    def tru_code(self, value):
        """Устанавливает tru_code модели ElectronicCertificateApprovedPaymentArticle.

        :param value: tru_code модели ElectronicCertificateApprovedPaymentArticle.
        :type value: str
        """
        self.__tru_code = value

    @property
    def article_code(self):
        """Возвращает article_code модели ElectronicCertificateApprovedPaymentArticle.

        :return: article_code модели ElectronicCertificateApprovedPaymentArticle.
        :rtype: str
        """
        return self.__article_code

    @article_code.setter
    def article_code(self, value):
        """Устанавливает article_code модели ElectronicCertificateApprovedPaymentArticle.

        :param value: article_code модели ElectronicCertificateApprovedPaymentArticle.
        :type value: str
        """
        self.__article_code = value

    @property
    def certificates(self):
        """Возвращает certificates модели ElectronicCertificateApprovedPaymentArticle.

        :return: certificates модели ElectronicCertificateApprovedPaymentArticle.
        :rtype: list[ElectronicCertificate]
        """
        return self.__certificates

    @certificates.setter
    def certificates(self, value):
        """Устанавливает certificates модели ElectronicCertificateApprovedPaymentArticle.

        :param value: certificates модели ElectronicCertificateApprovedPaymentArticle.
        :type value: list[ElectronicCertificate]
        """
        if isinstance(value, list):
            certificates_array = []
            for certificatesData in value:
                if isinstance(certificatesData, dict):
                    certificates_array.append(ElectronicCertificate(certificatesData))
                elif isinstance(certificatesData, ElectronicCertificate):
                    certificates_array.append(certificatesData)
                else:
                    raise TypeError('Invalid certificates data type in ElectronicCertificateApprovedPaymentArticle.certificates')

            self.__certificates = certificates_array
        else:
            raise TypeError('Invalid certificates value type in ElectronicCertificateApprovedPaymentArticle')



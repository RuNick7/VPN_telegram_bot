# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class ElectronicCertificateRefundArticle(BaseObject):
    """Товарная позиция в корзине возврата при возврате на электронный сертификат."""  # noqa: E501

    __article_number = None
    """Порядковый номер товара в корзине возврата. От 1 до 999 включительно."""

    __payment_article_number = None
    """Порядковый номер товара в одобренной корзине покупки (article_number в [объекте платежа](https://yookassa.ru/developers/api#payment_object)). От 1 до 999 включительно."""

    __tru_code = None
    """Код ТРУ. 30 символов, две группы цифр, разделенные точкой. Формат: ~`NNNNNNNNN.NNNNNNNNNYYYYMMMMZZZ`, где ~`NNNNNNNNN.NNNNNNNNN` — код вида ТРУ по [Перечню ТРУ](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1), ~`YYYY` — код производителя, ~`MMMM` — код модели, ~`ZZZ` — код страны производителя. Пример: ~`329921120.06001010200080001643`  [Как сформировать код ТРУ](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payments-preparations-tru-code) """  # noqa: E501

    __quantity = None
    """Количество возвращаемых единиц товара. Формат: целое положительное число. """  # noqa: E501

    @property
    def article_number(self):
        """Возвращает article_number модели ElectronicCertificateRefundArticle.

        :return: article_number модели ElectronicCertificateRefundArticle.
        :rtype: int
        """
        return self.__article_number

    @article_number.setter
    def article_number(self, value):
        """Устанавливает article_number модели ElectronicCertificateRefundArticle.

        :param value: article_number модели ElectronicCertificateRefundArticle.
        :type value: int
        """
        self.__article_number = value

    @property
    def payment_article_number(self):
        """Возвращает payment_article_number модели ElectronicCertificateRefundArticle.

        :return: payment_article_number модели ElectronicCertificateRefundArticle.
        :rtype: int
        """
        return self.__payment_article_number

    @payment_article_number.setter
    def payment_article_number(self, value):
        """Устанавливает payment_article_number модели ElectronicCertificateRefundArticle.

        :param value: payment_article_number модели ElectronicCertificateRefundArticle.
        :type value: int
        """
        self.__payment_article_number = value

    @property
    def tru_code(self):
        """Возвращает tru_code модели ElectronicCertificateRefundArticle.

        :return: tru_code модели ElectronicCertificateRefundArticle.
        :rtype: str
        """
        return self.__tru_code

    @tru_code.setter
    def tru_code(self, value):
        """Устанавливает tru_code модели ElectronicCertificateRefundArticle.

        :param value: tru_code модели ElectronicCertificateRefundArticle.
        :type value: str
        """
        self.__tru_code = value

    @property
    def quantity(self):
        """Возвращает quantity модели ElectronicCertificateRefundArticle.

        :return: quantity модели ElectronicCertificateRefundArticle.
        :rtype: int
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """Устанавливает quantity модели ElectronicCertificateRefundArticle.

        :param value: quantity модели ElectronicCertificateRefundArticle.
        :type value: int
        """
        self.__quantity = value



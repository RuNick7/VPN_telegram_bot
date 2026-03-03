# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class ElectronicCertificateArticle(BaseObject):
    """Товарная позиция в корзине покупки при оплате по электронному сертификату."""  # noqa: E501

    __article_number = None
    """Порядковый номер товара в корзине. От 1 до 999 включительно. """  # noqa: E501

    __tru_code = None
    """Код ТРУ. 30 символов, две группы цифр, разделенные точкой. Формат: ~`NNNNNNNNN.NNNNNNNNNYYYYMMMMZZZ`, где ~`NNNNNNNNN.NNNNNNNNN` — код вида ТРУ по [Перечню ТРУ](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1), ~`YYYY` — код производителя, ~`MMMM` — код модели, ~`ZZZ` — код страны производителя. Пример: ~`329921120.06001010200080001643`  [Как сформировать код ТРУ](/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payments-preparations-tru-code) """  # noqa: E501

    __article_code = None
    """Код товара в вашей системе. Максимум 128 символов. """  # noqa: E501

    __article_name = None
    """Название товара в вашей системе. Отображается на готовой платежной форме ЮKassa. Максимум 128 символов. """  # noqa: E501

    __quantity = None
    """Количество единиц товара. Формат: целое положительное число. """  # noqa: E501

    __price = None
    """Цена за единицу товара."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def article_number(self):
        """Возвращает article_number модели ElectronicCertificateArticle.

        :return: article_number модели ElectronicCertificateArticle.
        :rtype: int
        """
        return self.__article_number

    @article_number.setter
    def article_number(self, value):
        """Устанавливает article_number модели ElectronicCertificateArticle.

        :param value: article_number модели ElectronicCertificateArticle.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `article_number`, must not be `None`")  # noqa: E501
        if value is not None and value > 999:  # noqa: E501
            raise ValueError("Invalid value for `article_number`, must be a value less than or equal to `999`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `article_number`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__article_number = value

    @property
    def tru_code(self):
        """Возвращает tru_code модели ElectronicCertificateArticle.

        :return: tru_code модели ElectronicCertificateArticle.
        :rtype: str
        """
        return self.__tru_code

    @tru_code.setter
    def tru_code(self, value):
        """Устанавливает tru_code модели ElectronicCertificateArticle.

        :param value: tru_code модели ElectronicCertificateArticle.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `tru_code`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 30:
            raise ValueError("Invalid value for `tru_code`, length must be less than or equal to `30`")  # noqa: E501
        if value is not None and len(value) < 30:
            raise ValueError("Invalid value for `tru_code`, length must be greater than or equal to `30`")  # noqa: E501
        self.__tru_code = value

    @property
    def article_code(self):
        """Возвращает article_code модели ElectronicCertificateArticle.

        :return: article_code модели ElectronicCertificateArticle.
        :rtype: str
        """
        return self.__article_code

    @article_code.setter
    def article_code(self, value):
        """Устанавливает article_code модели ElectronicCertificateArticle.

        :param value: article_code модели ElectronicCertificateArticle.
        :type value: str
        """
        if value is not None and len(value) > 128:
            raise ValueError("Invalid value for `article_code`, length must be less than or equal to `128`")  # noqa: E501
        self.__article_code = value

    @property
    def article_name(self):
        """Возвращает article_name модели ElectronicCertificateArticle.

        :return: article_name модели ElectronicCertificateArticle.
        :rtype: str
        """
        return self.__article_name

    @article_name.setter
    def article_name(self, value):
        """Устанавливает article_name модели ElectronicCertificateArticle.

        :param value: article_name модели ElectronicCertificateArticle.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `article_name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 128:
            raise ValueError("Invalid value for `article_name`, length must be less than or equal to `128`")  # noqa: E501
        self.__article_name = value

    @property
    def quantity(self):
        """Возвращает quantity модели ElectronicCertificateArticle.

        :return: quantity модели ElectronicCertificateArticle.
        :rtype: int
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """Устанавливает quantity модели ElectronicCertificateArticle.

        :param value: quantity модели ElectronicCertificateArticle.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `quantity`, must not be `None`")  # noqa: E501
        self.__quantity = value

    @property
    def price(self):
        """Возвращает price модели ElectronicCertificateArticle.

        :return: price модели ElectronicCertificateArticle.
        :rtype: ElectronicCertificateArticlePrice
        """
        return self.__price

    @price.setter
    def price(self, value):
        """Устанавливает price модели ElectronicCertificateArticle.

        :param value: price модели ElectronicCertificateArticle.
        :type value: ElectronicCertificateArticlePrice
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `price`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__price = Amount(value)
        elif isinstance(value, Amount):
            self.__price = value
        else:
            raise TypeError('Invalid price data type in ElectronicCertificateArticle.price')

    @property
    def metadata(self):
        """Возвращает metadata модели ElectronicCertificateArticle.

        :return: metadata модели ElectronicCertificateArticle.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели ElectronicCertificateArticle.

        :param value: metadata модели ElectronicCertificateArticle.
        :type value: dict[str, str]
        """
        self.__metadata = value



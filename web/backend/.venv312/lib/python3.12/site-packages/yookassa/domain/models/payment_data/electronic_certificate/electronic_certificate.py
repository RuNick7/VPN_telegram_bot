# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class ElectronicCertificate(BaseObject):
    """Описание используемого электронного сертификата."""  # noqa: E501

    __certificate_id = None
    """Идентификатор сертификата. От 20 до 30 символов. """  # noqa: E501

    __tru_quantity = None
    """Количество единиц товара, которое одобрили для оплаты по этому электронному сертификату."""  # noqa: E501

    __available_compensation = None
    """
    Максимально допустимая сумма, которую может покрыть электронный сертификат для оплаты одной единицы товара.
    Пример: сертификат может компенсировать максимум 1000 рублей для оплаты этого товара.
    """  # noqa: E501

    __applied_compensation = None
    """
    Сумма, которую одобрили для оплаты по сертификату за одну единицу товара.
    Пример: из 1000 рублей одобрили 500 рублей для оплаты по сертификату.
    """  # noqa: E501

    @property
    def certificate_id(self):
        """Возвращает certificate_id модели ElectronicCertificate.

        :return: certificate_id модели ElectronicCertificate.
        :rtype: str
        """
        return self.__certificate_id

    @certificate_id.setter
    def certificate_id(self, value):
        """Устанавливает certificate_id модели ElectronicCertificate.

        :param value: certificate_id модели ElectronicCertificate.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `certificate_id`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 30:
            raise ValueError("Invalid value for `certificate_id`, length must be less than or equal to `30`")  # noqa: E501
        if value is not None and len(value) < 20:
            raise ValueError("Invalid value for `certificate_id`, length must be greater than or equal to `20`")  # noqa: E501
        self.__certificate_id = value

    @property
    def tru_quantity(self):
        """Возвращает tru_quantity модели ElectronicCertificate.

        :return: tru_quantity модели ElectronicCertificate.
        :rtype: int
        """
        return self.__tru_quantity

    @tru_quantity.setter
    def tru_quantity(self, value):
        """Устанавливает tru_quantity модели ElectronicCertificate.

        :param value: tru_quantity модели ElectronicCertificate.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `tru_quantity`, must not be `None`")  # noqa: E501
        self.__tru_quantity = value

    @property
    def available_compensation(self):
        """Возвращает available_compensation модели ElectronicCertificate.

        :return: available_compensation модели ElectronicCertificate.
        :rtype: ElectronicCertificateAvailableCompensation
        """
        return self.__available_compensation

    @available_compensation.setter
    def available_compensation(self, value):
        """Устанавливает available_compensation модели ElectronicCertificate.

        :param value: available_compensation модели ElectronicCertificate.
        :type value: ElectronicCertificateAvailableCompensation
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `available_compensation`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__available_compensation = Amount(value)
        elif isinstance(value, Amount):
            self.__available_compensation = value
        else:
            raise TypeError('Invalid available_compensation data type in ElectronicCertificate.available_compensation')

    @property
    def applied_compensation(self):
        """Возвращает applied_compensation модели ElectronicCertificate.

        :return: applied_compensation модели ElectronicCertificate.
        :rtype: ElectronicCertificateAppliedCompensation
        """
        return self.__applied_compensation

    @applied_compensation.setter
    def applied_compensation(self, value):
        """Устанавливает applied_compensation модели ElectronicCertificate.

        :param value: applied_compensation модели ElectronicCertificate.
        :type value: ElectronicCertificateAppliedCompensation
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `applied_compensation`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__applied_compensation = Amount(value)
        elif isinstance(value, Amount):
            self.__applied_compensation = value
        else:
            raise TypeError('Invalid applied_compensation data type in ElectronicCertificate.applied_compensation')



# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class IndustryDetails(BaseObject):
    """
    Данные отраслевого реквизита.
    """  # noqa: E501

    __federal_id = None
    """Идентификатор федерального органа исполнительной власти (тег в 54 ФЗ — 1262)."""  # noqa: E501

    __document_date = None
    """Дата документа основания (тег в 54 ФЗ — 1263). Передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) """  # noqa: E501

    __document_number = None
    """Номер нормативного акта федерального органа исполнительной власти, регламентирующего порядок заполнения реквизита «значение отраслевого реквизита» (тег в 54 ФЗ — 1264). """  # noqa: E501

    __value = None
    """Значение отраслевого реквизита (тег в 54 ФЗ — 1265)."""  # noqa: E501

    @property
    def federal_id(self):
        """
        Возвращает federal_id модели IndustryDetails.

        :return: federal_id модели IndustryDetails.
        :rtype: str
        """
        return self.__federal_id

    @federal_id.setter
    def federal_id(self, value):
        """
        Устанавливает federal_id модели IndustryDetails.

        :param value: federal_id модели IndustryDetails.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `federal_id`, must not be `None`")  # noqa: E501
        if value is not None and not re.search(r'(^00[1-9]{1}$)|(^0[1-6]{1}[0-9]{1}$)|(^07[0-3]{1}$)', value):  # noqa: E501
            raise ValueError(r"Invalid value for `federal_id`, must be a follow pattern or equal to `/(^00[1-9]{1}$)|(^0[1-6]{1}[0-9]{1}$)|(^07[0-3]{1}$)/`")  # noqa: E501
        self.__federal_id = value

    @property
    def document_date(self):
        """
        Возвращает document_date модели IndustryDetails.

        :return: document_date модели IndustryDetails.
        :rtype: date
        """
        return self.__document_date

    @document_date.setter
    def document_date(self, value):
        """
        Устанавливает document_date модели IndustryDetails.

        :param value: document_date модели IndustryDetails.
        :type value: date
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `document_date`, must not be `None`")  # noqa: E501
        self.__document_date = value

    @property
    def document_number(self):
        """
        Возвращает document_number модели IndustryDetails.

        :return: document_number модели IndustryDetails.
        :rtype: str
        """
        return self.__document_number

    @document_number.setter
    def document_number(self, value):
        """
        Устанавливает document_number модели IndustryDetails.

        :param value: document_number модели IndustryDetails.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `document_number`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 32:
            raise ValueError("Invalid value for `document_number`, length must be less than or equal to `32`")  # noqa: E501
        self.__document_number = value

    @property
    def value(self):
        """
        Возвращает value модели IndustryDetails.

        :return: value модели IndustryDetails.
        :rtype: str
        """
        return self.__value

    @value.setter
    def value(self, value):
        """
        Устанавливает value модели IndustryDetails.

        :param value: value модели IndustryDetails.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `value`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 256:
            raise ValueError("Invalid value for `value`, length must be less than or equal to `256`")  # noqa: E501
        self.__value = value

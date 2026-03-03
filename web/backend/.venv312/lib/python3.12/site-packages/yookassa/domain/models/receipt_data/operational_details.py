# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class OperationalDetails(BaseObject):
    """
    Данные операционного реквизита чека
    """  # noqa: E501

    __operation_id = None
    """Идентификатор операции (тег в 54 ФЗ — 1271). Число от 0 до 255. """  # noqa: E501

    __value = None
    """Данные операции (тег в 54 ФЗ — 1272)."""  # noqa: E501

    __created_at = None
    """Время создания операции (тег в 54 ФЗ — 1273). Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    @property
    def operation_id(self):
        """
        Возвращает operation_id модели OperationalDetails.

        :return: operation_id модели OperationalDetails.
        :rtype: int
        """
        return self.__operation_id

    @operation_id.setter
    def operation_id(self, value):
        """
        Устанавливает operation_id модели OperationalDetails.

        :param value: operation_id модели OperationalDetails.
        :type value: int
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `operation_id`, must not be `None`")  # noqa: E501
        if not isinstance(value, int):  # noqa: E501
            raise TypeError("Invalid value type for `operation_id`, must be `int`")  # noqa: E501
        if value is not None and value > 255:  # noqa: E501
            raise ValueError("Invalid value for `operation_id`, must be a value less than or equal to `255`")  # noqa: E501
        if value is not None and value < 0:  # noqa: E501
            raise ValueError("Invalid value for `operation_id`, must be a value greater than or equal to `0`")  # noqa: E501
        self.__operation_id = value

    @property
    def value(self):
        """
        Возвращает value модели OperationalDetails.

        :return: value модели OperationalDetails.
        :rtype: str
        """
        return self.__value

    @value.setter
    def value(self, value):
        """
        Устанавливает value модели OperationalDetails.

        :param value: value модели OperationalDetails.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `value`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 64:
            raise ValueError("Invalid value for `value`, length must be less than or equal to `64`")  # noqa: E501
        self.__value = value

    @property
    def created_at(self):
        """
        Возвращает created_at модели OperationalDetails.

        :return: created_at модели OperationalDetails.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели OperationalDetails.

        :param value: created_at модели OperationalDetails.
        :type value: datetime
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `created_at`, must not be `None`")  # noqa: E501
        self.__created_at = value

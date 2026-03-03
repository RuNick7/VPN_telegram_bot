# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class RequestRefundData(BaseObject):
    """
    Базовый класс генерируемых объектов ResponseRefundData.
    """  # noqa: E501

    __type = None
    """Код способа оплаты."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели ResponseRefundData.

        :return: type модели ResponseRefundData.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели ResponseRefundData.

        :param value: type модели ResponseRefundData.
        :type value: str
        """
        self.__type = str(value)


class ResponseRefundData(BaseObject):
    """
    Базовый класс генерируемых объектов ResponseRefundData.
    """  # noqa: E501

    __type = None
    """Код способа оплаты."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели ResponseRefundData.

        :return: type модели ResponseRefundData.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели ResponseRefundData.

        :param value: type модели ResponseRefundData.
        :type value: str
        """
        self.__type = str(value)

# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class PayoutDestination(BaseObject):
    """
    Базовый класс генерируемых объектов PayoutDestination.
    """  # noqa: E501

    __type = None
    """Тип метода оплаты."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели PayoutDestination.

        :return: type модели PayoutDestination.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели PayoutDestination.

        :param value: type модели PayoutDestination.
        :type value: str
        """
        self.__type = str(value)

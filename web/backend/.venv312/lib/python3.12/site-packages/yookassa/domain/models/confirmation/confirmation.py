# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class Confirmation(BaseObject):
    """
    Базовый класс генерируемых объектов Confirmation.
    """  # noqa: E501

    __type = None
    """Код сценария подтверждения.""" # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели Confirmation.

        :return: type модели Confirmation.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели Confirmation.

        :param value: type модели Confirmation.
        :type value: str
        """
        self.__type = str(value)

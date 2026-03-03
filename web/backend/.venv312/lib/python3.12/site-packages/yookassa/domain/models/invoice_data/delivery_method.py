# coding: utf-8

from yookassa.domain.common import BaseObject


class DeliveryMethod(BaseObject):
    """Данные о выбранном способе доставки счета. Присутствует только для счетов в статусе ~`pending`. """  # noqa: E501

    __type = None
    """Код способа доставки счета пользователю"""

    @property
    def type(self):
        """Возвращает type модели DeliveryMethod.

        :return: type модели DeliveryMethod.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели DeliveryMethod.

        :param value: type модели DeliveryMethod.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = value



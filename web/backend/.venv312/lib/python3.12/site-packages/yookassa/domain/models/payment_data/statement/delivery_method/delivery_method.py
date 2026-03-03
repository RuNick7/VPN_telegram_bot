# -*- coding: utf-8 -*-
from yookassa.domain.common import RequestObject


class DeliveryMethod(RequestObject):
    """
    Данные о выбранном способе доставки справки.
    """  # noqa: E501

    __type = None
    """Тип способа доставки справки. """ # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели DeliveryMethod.

        :return: type модели DeliveryMethod.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели DeliveryMethod.

        :param value: type модели DeliveryMethod.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = str(value)

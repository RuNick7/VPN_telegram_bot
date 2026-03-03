# -*- coding: utf-8 -*-
from yookassa.domain.common import RequestObject


class Statement(RequestObject):
    """
    Данные для отправки справки. Необходимо передавать, если вы хотите, чтобы после оплаты пользователь получил справку. Сейчас доступен один тип справок — квитанция по платежу. Это информация об успешном платеже, которую ЮKassa отправляет на электронную почту пользователя.
    """  # noqa: E501

    __type = None
    """Тип справки."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели Statement.

        :return: type модели Statement.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели Statement.

        :param value: type модели Statement.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = str(value)

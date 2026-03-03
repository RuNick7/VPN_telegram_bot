# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class SelfEmployedConfirmation(BaseObject):
    """
    Базовый класс генерируемых объектов SelfEmployedConfirmation.
    """  # noqa: E501

    __type = None
    """Код сценария подтверждения."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели SelfEmployedConfirmation.

        :return: type модели SelfEmployedConfirmation.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели SelfEmployedConfirmation.

        :param value: type модели SelfEmployedConfirmation.
        :type value: str
        """
        self.__type = str(value)


class SelfEmployedConfirmationType:
    """
    Код сценария подтверждения пользователем заявки ЮMoney на получение прав для регистрации чеков в сервисе Мой налог. 
    """  # noqa: E501

    """
    Список допустимых значений
    """
    REDIRECT = 'redirect'
    """Необходимо направить плательщика на страницу партнера."""

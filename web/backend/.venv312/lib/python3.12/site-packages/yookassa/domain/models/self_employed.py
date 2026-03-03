# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PayoutSelfEmployed(BaseObject):
    """Данные самозанятого, который получит выплату. Только для обычных выплат. Устаревший параметр. Раньше использовался для выплат самозанятым. Сейчас функциональность недоступна. Параметр сохранен для поддержки обратной совместимости, в новых версиях API может быть удален."""  # noqa: E501

    __id = None
    """Идентификатор самозанятого в ЮKassa."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PayoutSelfEmployed.

        :return: id модели PayoutSelfEmployed.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PayoutSelfEmployed.

        :param value: id модели PayoutSelfEmployed.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `id`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 50:
            raise ValueError("Invalid value for `id`, length must be less than or equal to `50`")  # noqa: E501
        if value is not None and len(value) < 36:
            raise ValueError("Invalid value for `id`, length must be greater than or equal to `36`")  # noqa: E501
        self.__id = value


class SelfEmployedStatus(object):
    """
    Статус подключения самозанятого и выдачи ЮMoney прав на регистрацию чеков
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PENDING = "pending"
    """ЮMoney запросили права на регистрацию чеков, но самозанятый еще не ответил на заявку"""
    CONFIRMED = "confirmed"
    """Самозанятый выдал права ЮMoney; вы можете делать выплаты"""
    CANCELED = "canceled"
    """Самозанятый отклонил заявку или отозвал ранее выданные права"""
    UNREGISTERED = "unregistered"
    """Самозанятый с таким ИНН не зарегистрирован в сервисе Мой налог, или пользователь потерял статус самозанятого"""

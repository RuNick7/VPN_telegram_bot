# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class FiscalizationData(BaseObject):
    """
    Настройки магазина для %[отправки чеков в налоговую](/developers/payment-acceptance/receipts/basics).
    Присутствует, если вы запрашивали настройки магазина и этот магазин использует решения ЮKassa для отправки чеков. Отсутствует, если магазин еще не включал отправку чеков через ЮKassa.
    """  # noqa: E501

    __enabled = None
    """В настройках магазина включена отправка чеков. Возможные значения:  * ~`true` — магазин отправляет данные для чеков через ЮKassa; * ~`false` — магазин выключил отправку чеков через ЮKassa. """  # noqa: E501

    __provider = None
    """Решение ЮKassa, которое магазин использует для отправки чеков."""  # noqa: E501

    @property
    def enabled(self):
        """
        Возвращает enabled модели FiscalizationData.

        :return: enabled модели FiscalizationData.
        :rtype: bool
        """
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        """
        Устанавливает enabled модели FiscalizationData.

        :param value: enabled модели FiscalizationData.
        :type value: bool
        """
        self.__enabled = value

    @property
    def provider(self):
        """
        Возвращает provider модели FiscalizationData.

        :return: provider модели FiscalizationData.
        :rtype: str
        """
        return self.__provider

    @provider.setter
    def provider(self, value):
        """
        Устанавливает provider модели FiscalizationData.

        :param value: provider модели FiscalizationData.
        :type value: str
        """
        self.__provider = value

# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class PaymentData(BaseObject):
    """
    Базовый класс генерируемых объектов Payment.
    """  # noqa: E501

    __type = None
    """Тип метода оплаты."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели PaymentData.

        :return: type модели PaymentData.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели PaymentData.

        :param value: type модели PaymentData.
        :type value: str
        """
        self.__type = str(value)


class ResponsePaymentData(PaymentData):
    """
    Класс, описывающий основные свойства и методы платежных методов.
    """  # noqa: E501

    __id = None
    """Идентификатор способа оплаты."""  # noqa: E501

    __saved = None
    """
    Признак сохранения способа оплаты для %[автоплатежей](/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Возможные значения:
    ~`true` — способ оплаты сохранен для автоплатежей и выплат;
    ~`false` — способ оплаты не сохранен.
    """  # noqa: E501

    __title = None
    """Название способа оплаты."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели ResponsePaymentData.

        :return: id модели ResponsePaymentData.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели ResponsePaymentData.

        :param value: id модели ResponsePaymentData.
        :type value: str
        """
        self.__id = str(value)

    @property
    def saved(self):
        """
        Возвращает saved модели ResponsePaymentData.

        :return: saved модели ResponsePaymentData.
        :rtype: bool
        """
        return self.__saved

    @saved.setter
    def saved(self, value):
        """
        Устанавливает saved модели ResponsePaymentData.

        :param value: saved модели ResponsePaymentData.
        :type value: bool
        """
        self.__saved = bool(value)

    @property
    def title(self):
        """
        Возвращает title модели ResponsePaymentData.

        :return: title модели ResponsePaymentData.
        :rtype: str
        """
        return self.__title

    @title.setter
    def title(self, value):
        """
        Устанавливает title модели ResponsePaymentData.

        :param value: title модели ResponsePaymentData.
        :type value: str
        """
        self.__title = str(value)


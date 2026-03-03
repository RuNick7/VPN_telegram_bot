# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.notification.webhook_notification_types import WebhookNotificationType, \
    WebhookNotificationEventType
from yookassa.domain.response import DealResponse
from yookassa.domain.response.payment_response import PaymentResponse
from yookassa.domain.response.payout_response import PayoutResponse
from yookassa.domain.response.refund_response import RefundResponse


class WebhookNotification(BaseObject):
    """
    Базовый класс генерируемых объектов WebhookNotification.
    """  # noqa: E501

    __type = None
    """Тип уведомления."""  # noqa: E501

    __event = None
    """Событие, о котором уведомляет ЮKassa."""  # noqa: E501

    __object = None
    """Объект, с которым произошло событие: payment — платеж, refund — возврат, payout — выплата, deal — сделка."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели WebhookNotification.

        :return: type модели WebhookNotification.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели WebhookNotification.

        :param value: type модели WebhookNotification.
        :type value: str
        """
        self.__type = value

    @property
    def event(self):
        """
        Возвращает event модели WebhookNotification.

        :return: event модели WebhookNotification.
        :rtype: str
        """
        return self.__event

    @event.setter
    def event(self, value):
        """
        Устанавливает event модели WebhookNotification.

        :param value: event модели WebhookNotification.
        :type value: str
        """
        self.__event = value

    @property
    def object(self):
        """
        Возвращает object модели WebhookNotification.

        :return: object модели WebhookNotification.
        :rtype: PaymentResponse
        """
        return self.__object

    @object.setter
    def object(self, value):
        """
        Устанавливает object модели WebhookNotification.

        :param value: object модели WebhookNotification.
        :type value: PaymentResponse
        """
        if isinstance(value, dict) and value:
            self.__object = PaymentResponse(value)
        elif not value:
            raise ValueError('Parameter object is empty')
        else:
            raise TypeError('Invalid object type')


class PaymentWebhookNotification(WebhookNotification):
    """
    Объект с информацией о платеже, уведомление о котором хранится в текущем объекте.
    """  # noqa: E501
    pass


class RefundWebhookNotification(WebhookNotification):
    """
    Объект с информацией о возврате, уведомление о котором хранится в текущем объекте.
    """  # noqa: E501

    @property
    def object(self):
        """
        Возвращает object модели RefundWebhookNotification.

        :return: object модели RefundWebhookNotification.
        :rtype: RefundResponse
        """
        return self.__object

    @object.setter
    def object(self, value):
        """
        Устанавливает object модели RefundWebhookNotification.

        :param value: object модели RefundWebhookNotification.
        :type value: RefundResponse
        """
        if isinstance(value, dict) and value:
            self.__object = RefundResponse(value)
        elif not value:
            raise ValueError('Parameter object is empty')
        else:
            raise TypeError('Invalid object type')


class DealWebhookNotification(WebhookNotification):
    """
    Объект с информацией о сделке, уведомление о котором хранится в текущем объекте.
    """  # noqa: E501

    @property
    def object(self):
        """
        Возвращает object модели DealWebhookNotification.

        :return: object модели DealWebhookNotification.
        :rtype: DealResponse
        """
        return self.__object

    @object.setter
    def object(self, value):
        """
        Устанавливает object модели DealWebhookNotification.

        :param value: object модели DealWebhookNotification.
        :type value: DealResponse
        """
        if isinstance(value, dict) and value:
            self.__object = DealResponse(value)
        elif not value:
            raise ValueError('Parameter object is empty')
        else:
            raise TypeError('Invalid object type')


class PayoutWebhookNotification(WebhookNotification):
    """
    Объект с информацией о выплате, уведомление о котором хранится в текущем объекте.
    """  # noqa: E501

    @property
    def object(self):
        """
        Возвращает object модели PayoutWebhookNotification.

        :return: object модели PayoutWebhookNotification.
        :rtype: PayoutResponse
        """
        return self.__object

    @object.setter
    def object(self, value):
        """
        Устанавливает object модели PayoutWebhookNotification.

        :param value: object модели PayoutWebhookNotification.
        :type value: PayoutResponse
        """
        if isinstance(value, dict) and value:
            self.__object = PayoutResponse(value)
        elif not value:
            raise ValueError('Parameter object is empty')
        else:
            raise TypeError('Invalid object type')


class WebhookNotificationFactory(object):
    """
    Фабрика создания объекта WebhookNotification по типу.
    """  # noqa: E501

    def create(self, data):
        """
        Создание экземпляра из данных

        :param data: словарь с данными type и event
        :return: Экземпляр объекта по типу
        """
        if isinstance(data, dict):
            if 'type' in data and 'event' in data:
                return self.__get_instance(data)
            else:
                raise ValueError('Parameter "data" should contain "type" and "event" fields')
        else:
            raise TypeError('Parameter "data" should be "dict"')

    def __get_instance(self, data):
        """
        Получение экземпляра из данных

        :param data: словарь с данными type и event
        :return: Экземпляр объекта по типу
        """
        class_object = self.__get_class_object(data)
        return class_object(data)

    @staticmethod
    def __get_class_object(data):
        """
        Получение экземпляра из данных

        :param data: словарь с данными type и event
        :return: Экземпляр объекта по типу
        """
        if data['type'] == WebhookNotificationType.NOTIFICATION:
            if data['event'] == WebhookNotificationEventType.REFUND_SUCCEEDED:
                return RefundWebhookNotification
            elif data['event'] == WebhookNotificationEventType.DEAL_CLOSED:
                return DealWebhookNotification
            elif data['event'] == WebhookNotificationEventType.PAYOUT_SUCCEEDED or \
                    data['event'] == WebhookNotificationEventType.PAYOUT_CANCELED:
                return PayoutWebhookNotification
            else:
                return WebhookNotification
        else:
            raise TypeError('Parameter "data" should contain "type" field')

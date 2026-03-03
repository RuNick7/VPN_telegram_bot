# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject


class WebhookRequest(RequestObject):
    """
    Объект запроса к API на создание вебхука.
    """  # noqa: E501

    __event = None
    """Событие, которое хотите отслеживать."""  # noqa: E501

    __url = None
    """URL, на который ЮKassa будет отправлять уведомления."""  # noqa: E501

    @property
    def event(self):
        """
        Возвращает event модели WebhookRequest.

        :return: event модели WebhookRequest.
        :rtype: str
        """
        return self.__event

    @event.setter
    def event(self, value):
        """
        Устанавливает event модели WebhookRequest.

        :param value: event модели WebhookRequest.
        :type value: str
        """
        cast_value = str(value)
        self.__event = cast_value

    @property
    def url(self):
        """
        Возвращает url модели WebhookRequest.

        :return: url модели WebhookRequest.
        :rtype: str
        """
        return self.__url

    @url.setter
    def url(self, value):
        """
        Устанавливает url модели WebhookRequest.

        :param value: url модели WebhookRequest.
        :type value: str
        """
        cast_value = str(value)
        self.__url = cast_value

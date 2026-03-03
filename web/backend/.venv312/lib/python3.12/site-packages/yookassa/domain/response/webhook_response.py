# -*- coding: utf-8 -*-
from yookassa.domain.common.response_object import ResponseObject


class WebhookResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о вебхуке.
    """  # noqa: E501

    __id = None
    """Идентификатор webhook."""  # noqa: E501

    __url = None
    """URL, на который ЮKassa отправляет уведомления."""  # noqa: E501

    __event = None
    """Событие, о котором уведомляет ЮKassa."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели WebhookResponse.

        :return: id модели WebhookResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели WebhookResponse.

        :param value: id модели WebhookResponse.
        :type value: str
        """
        self.__id = value

    @property
    def event(self):
        """
        Возвращает event модели WebhookResponse.

        :return: event модели WebhookResponse.
        :rtype: str
        """
        return self.__event

    @event.setter
    def event(self, value):
        """
        Устанавливает event модели WebhookResponse.

        :param value: event модели WebhookResponse.
        :type value: str
        """
        self.__event = value

    @property
    def url(self):
        """
        Возвращает url модели WebhookResponse.

        :return: url модели WebhookResponse.
        :rtype: str
        """
        return self.__url

    @url.setter
    def url(self, value):
        """
        Устанавливает url модели WebhookResponse.

        :param value: url модели WebhookResponse.
        :type value: str
        """
        self.__url = value


class WebhookList(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе списка вебхуков.
    """  # noqa: E501

    __type = None
    """Формат выдачи результатов запроса. Возможное значение: `list` (список). """  # noqa: E501

    __items = None
    """Массив вебхуков."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели WebhookList.

        :return: type модели WebhookList.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели WebhookList.

        :param value: type модели WebhookList.
        :type value: str
        """
        self.__type = value

    @property
    def items(self):
        """
        Возвращает items модели WebhookList.

        :return: items модели WebhookList.
        :rtype: list[WebhookResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели WebhookList.

        :param value: items модели WebhookList.
        :type value: list[WebhookResponse]
        """
        if isinstance(value, list):
            self.__items = [WebhookResponse(webhook) for webhook in value]
        else:
            self.__items = value




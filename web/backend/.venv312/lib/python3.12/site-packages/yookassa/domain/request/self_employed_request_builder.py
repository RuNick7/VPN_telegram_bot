# -*- coding: utf-8 -*-
from yookassa.domain.request import SelfEmployedRequest


class SelfEmployedRequestBuilder(object):
    """
    Конструктор запроса на создание объекта самозанятого.
    """  # noqa: E501

    def __init__(self):
        self.__request = SelfEmployedRequest()

    def set_itn(self, value):
        """
        Устанавливает itn модели SelfEmployedRequestBuilder.

        :param value: itn модели SelfEmployedRequestBuilder.
        :type value: str
        :rtype: SelfEmployedRequestBuilder
        """
        self.__request.itn = value
        return self

    def set_phone(self, value):
        """
        Устанавливает phone модели SelfEmployedRequestBuilder.

        :param value: phone модели SelfEmployedRequestBuilder.
        :type value: str
        :rtype: SelfEmployedRequestBuilder
        """
        self.__request.phone = value
        return self

    def set_description(self, value):
        """
        Устанавливает description модели SelfEmployedRequestBuilder.

        :param value: description модели SelfEmployedRequestBuilder.
        :type value: str
        :rtype: SelfEmployedRequestBuilder
        """
        self.__request.description = value
        return self

    def set_confirmation(self, value):
        """
        Устанавливает confirmation модели SelfEmployedRequestBuilder.

        :param value: confirmation модели SelfEmployedRequestBuilder.
        :type value: SelfEmployedConfirmation
        :rtype: SelfEmployedRequestBuilder
        """
        self.__request.confirmation = value
        return self

    def set_metadata(self, value):
        """
        Устанавливает payment_id модели SelfEmployedRequestBuilder.

        :param value: payment_id модели SelfEmployedRequestBuilder.
        :type value: dict[str, str]
        :rtype: SelfEmployedRequestBuilder
        """
        self.__request.metadata = value
        return self

    def build(self):
        """
        Возвращает request модели SelfEmployedRequestBuilder.

        :return: request модели SelfEmployedRequestBuilder.
        :rtype: SelfEmployedRequest
        """
        return self.__request

# -*- coding: utf-8 -*-
from yookassa.domain.request import DealRequest


class DealRequestBuilder(object):
    """
    Конструктор запроса на подтверждение оплаты.
    """  # noqa: E501

    def __init__(self):
        self.__request = DealRequest()

    def set_type(self, value):
        """
        Устанавливает type модели DealRequest.

        :param value: type модели DealRequest.
        :type value: str
        :rtype: DealRequestBuilder
        """
        self.__request.type = value
        return self

    def set_fee_moment(self, value):
        """
        Устанавливает fee_moment модели DealRequest.

        :param value: fee_moment модели DealRequest.
        :type value: str
        :rtype: DealRequestBuilder
        """
        self.__request.fee_moment = value
        return self

    def set_description(self, value):
        """
        Устанавливает description модели DealRequest.

        :param value: description модели DealRequest.
        :type value: str
        :rtype: DealRequestBuilder
        """
        self.__request.description = value
        return self

    def set_metadata(self, value):
        """
        Устанавливает metadata модели DealRequest.

        :param value: metadata модели DealRequest.
        :type value: dict[str, str]
        :rtype: DealRequestBuilder
        """
        self.__request.metadata = value
        return self

    def build(self):
        """
        Возвращает request модели DealRequestBuilder.

        :return: request модели DealRequestBuilder.
        :rtype: DealRequest
        """
        return self.__request

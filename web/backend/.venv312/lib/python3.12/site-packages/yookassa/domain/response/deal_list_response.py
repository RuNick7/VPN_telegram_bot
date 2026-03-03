# -*- coding: utf-8 -*-
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.response.deal_response import DealResponse


class DealListResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе списка сделок.
    """  # noqa: E501

    __type = None
    """Формат выдачи результатов запроса. Возможное значение: `list` (список). """  # noqa: E501

    __next_cursor = None
    """Указатель на следующий фрагмент списка. Обязательный параметр, если размер списка больше размера выдачи (`limit`) и конец выдачи не достигнут."""  # noqa: E501

    __items = None
    """Массив сделок."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели DealListResponse.

        :return: type модели DealListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели DealListResponse.

        :param value: type модели DealListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def next_cursor(self):
        """
        Возвращает next_cursor модели DealListResponse.

        :return: next_cursor модели DealListResponse.
        :rtype: str
        """
        return self.__next_cursor

    @next_cursor.setter
    def next_cursor(self, value):
        """
        Устанавливает next_cursor модели DealListResponse.

        :param value: next_cursor модели DealListResponse.
        :type value: str
        """
        self.__next_cursor = value

    @property
    def items(self):
        """
        Возвращает items модели DealListResponse.

        :return: items модели DealListResponse.
        :rtype: list[DealResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели DealListResponse.

        :param value: items модели DealListResponse.
        :type value: list[DealResponse]
        """
        if isinstance(value, list):
            self.__items = [DealResponse(payment) for payment in value]
        else:
            self.__items = value

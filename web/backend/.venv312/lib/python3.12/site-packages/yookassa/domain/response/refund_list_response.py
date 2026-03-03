# -*- coding: utf-8 -*-
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.response.refund_response import RefundResponse


class RefundListResponse(ResponseObject):
    """
    Список возвратов. Возвраты отсортированы по времени создания в порядке убывания (от новых к старым). Если результатов больше, чем задано в limit, список будет выводиться фрагментами. В этом случае в ответе на запрос вернется фрагмент списка и параметр next_cursor с указателем на следующий фрагмент.
    """  # noqa: E501

    __type = None
    """Формат выдачи результатов запроса. Возможное значение: ~`list` (список). """  # noqa: E501

    __items = None
    """Массив платежей."""  # noqa: E501

    __next_cursor = None
    """Указатель на следующий фрагмент списка. Обязательный параметр, если размер списка больше размера выдачи (`limit`) и конец выдачи не достигнут."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели RefundListResponse.

        :return: type модели RefundListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели RefundListResponse.

        :param value: type модели RefundListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def next_cursor(self):
        """
        Возвращает next_cursor модели RefundListResponse.

        :return: next_cursor модели RefundListResponse.
        :rtype: str
        """
        return self.__next_cursor

    @next_cursor.setter
    def next_cursor(self, value):
        """
        Устанавливает next_cursor модели RefundListResponse.

        :param value: next_cursor модели RefundListResponse.
        :type value: str
        """
        self.__next_cursor = value

    @property
    def items(self):
        """
        Возвращает items модели RefundListResponse.

        :return: items модели RefundListResponse.
        :rtype: list[RefundResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели RefundListResponse.

        :param value: items модели RefundListResponse.
        :type value: list[RefundResponse]
        """
        if isinstance(value, list):
            self.__items = [RefundResponse(refund) for refund in value]
        else:
            self.__items = value

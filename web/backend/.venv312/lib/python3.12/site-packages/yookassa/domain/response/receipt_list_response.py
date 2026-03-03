# -*- coding: utf-8 -*-
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.response.receipt_response import ReceiptResponse


class ReceiptListResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе списка чеков.
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
        Возвращает type модели ReceiptListResponse.

        :return: type модели ReceiptListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели ReceiptListResponse.

        :param value: type модели ReceiptListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def next_cursor(self):
        """
        Возвращает next_cursor модели ReceiptListResponse.

        :return: next_cursor модели ReceiptListResponse.
        :rtype: str
        """
        return self.__next_cursor

    @next_cursor.setter
    def next_cursor(self, value):
        """
        Устанавливает next_cursor модели ReceiptListResponse.

        :param value: next_cursor модели ReceiptListResponse.
        :type value: str
        """
        self.__next_cursor = value

    @property
    def items(self):
        """
        Возвращает items модели ReceiptListResponse.

        :return: items модели ReceiptListResponse.
        :rtype: list[ReceiptResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели ReceiptListResponse.

        :param value: items модели ReceiptListResponse.
        :type value: list[ReceiptResponse]
        """
        if isinstance(value, list):
            self.__items = [ReceiptResponse(receipt) for receipt in value]
        else:
            self.__items = value

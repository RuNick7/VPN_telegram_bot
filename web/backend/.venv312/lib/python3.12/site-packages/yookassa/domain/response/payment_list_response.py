# -*- coding: utf-8 -*-
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.response.payment_response import PaymentResponse


class PaymentListResponse(ResponseObject):
    """
    Список платежей. Платежи отсортированы по времени создания в порядке убывания (от новых к старым). Если результатов больше, чем задано в limit, список будет выводиться фрагментами. В этом случае в ответе на запрос вернется фрагмент списка и параметр next_cursor с указателем на следующий фрагмент.
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
        Возвращает type модели PaymentListResponse.

        :return: type модели PaymentListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели PaymentListResponse.

        :param value: type модели PaymentListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def next_cursor(self):
        """
        Возвращает next_cursor модели PaymentListResponse.

        :return: next_cursor модели PaymentListResponse.
        :rtype: str
        """
        return self.__next_cursor

    @next_cursor.setter
    def next_cursor(self, value):
        """
        Устанавливает next_cursor модели PaymentListResponse.

        :param value: next_cursor модели PaymentListResponse.
        :type value: str
        """
        self.__next_cursor = value

    @property
    def items(self):
        """
        Возвращает items модели PaymentListResponse.

        :return: items модели PaymentListResponse.
        :rtype: list[PaymentResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели PaymentListResponse.

        :param value: items модели PaymentListResponse.
        :type value: list[PaymentResponse]
        """
        if isinstance(value, list):
            self.__items = [PaymentResponse(payment) for payment in value]
        else:
            self.__items = value

# coding: utf-8
from yookassa.domain.response.payout_response import PayoutResponse
from yookassa.domain.common.response_object import ResponseObject


class PayoutListResponse(ResponseObject):
    """Список выплат. Выплаты отсортированы по времени создания в порядке убывания (от новых к старым). Если результатов больше, чем задано в limit, список будет выводиться фрагментами.  В этом случае в ответе на запрос вернется фрагмент списка и параметр next_cursor с указателем на следующий фрагмент. """  # noqa: E501

    __type = None
    """Формат выдачи результатов запроса.  Возможное значение: ~`list` (список). """  # noqa: E501

    __items = None

    __next_cursor = None
    """Указатель на следующий фрагмент списка. Обязательный параметр, если размер списка больше размера выдачи (`limit`) и конец выдачи не достигнут."""  # noqa: E501

    @property
    def type(self):
        """Возвращает type модели PayoutListResponse.

        :return: type модели PayoutListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели PayoutListResponse.

        :param value: type модели PayoutListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def items(self):
        """Возвращает items модели PayoutListResponse.

        :return: items модели PayoutListResponse.
        :rtype: list[Payout]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """Устанавливает items модели PayoutListResponse.

        :param value: items модели PayoutListResponse.
        :type value: list[Response]
        """
        if isinstance(value, list):
            self.__items = [PayoutResponse(payout) for payout in value]
        else:
            self.__items = value

    @property
    def next_cursor(self):
        """Возвращает next_cursor модели PayoutListResponse.

        :return: next_cursor модели PayoutListResponse.
        :rtype: str
        """
        return self.__next_cursor

    @next_cursor.setter
    def next_cursor(self, value):
        """Устанавливает next_cursor модели PayoutListResponse.

        :param value: next_cursor модели PayoutListResponse.
        :type value: str
        """
        self.__next_cursor = value

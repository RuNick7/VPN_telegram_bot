# coding: utf-8
from yookassa.domain.common import BaseObject
from yookassa.domain.models import SbpParticipantBank


class SbpBankListResponse(BaseObject):
    """
    Объект ответа, возвращаемого API при запросе списка участников СБП, отсортированный по идентификатору участника в порядке убывания (desc).
    """  # noqa: E501

    __type = None
    """Формат выдачи результатов запроса. Возможное значение: ~`list` (список). """  # noqa: E501

    __items = None
    """Массив платежей."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели SbpBankListResponse.

        :return: type модели SbpBankListResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели SbpBankListResponse.

        :param value: type модели SbpBankListResponse.
        :type value: str
        """
        self.__type = value

    @property
    def items(self):
        """
        Возвращает items модели SbpBankListResponse.

        :return: items модели SbpBankListResponse.
        :rtype: list[SbpParticipantBank]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели SbpBankListResponse.

        :param value: items модели SbpBankListResponse.
        :type value: list[SbpParticipantBank]
        """
        if isinstance(value, list):
            self.__items = [SbpParticipantBank(receipt) for receipt in value]
        else:
            self.__items = value

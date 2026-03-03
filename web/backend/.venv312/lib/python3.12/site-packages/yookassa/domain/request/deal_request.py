# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject

DESCRIPTION_MAX_LENGTH = 128


class DealRequest(RequestObject):
    """
    Объект запроса к API на проведение новой сделки.
    """  # noqa: E501

    __type = None
    """Тип сделки."""

    __fee_moment = None
    """Момент перечисления вам вознаграждения платформы."""

    __description = None
    """Описание сделки."""

    __metadata = None
    """Метаданные привязанные к сделке."""

    @property
    def type(self):
        """
        Возвращает type модели DealRequest.

        :return: type модели DealRequest.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели DealRequest.

        :param value: type модели DealRequest.
        :type value: str
        """
        self.__type = str(value)

    @property
    def fee_moment(self):
        """
        Возвращает fee_moment модели DealRequest.

        :return: fee_moment модели DealRequest.
        :rtype: str
        """
        return self.__fee_moment

    @fee_moment.setter
    def fee_moment(self, value):
        """
        Устанавливает fee_moment модели DealRequest.

        :param value: fee_moment модели DealRequest.
        :type value: str
        """
        self.__fee_moment = str(value)

    @property
    def description(self):
        """
        Возвращает description модели DealRequest.

        :return: description модели DealRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели DealRequest.

        :param value: description модели DealRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            if len(cast_value) <= DESCRIPTION_MAX_LENGTH:
                self.__description = cast_value
            else:
                raise ValueError('The value of the description parameter is too long. Max length is {}'.format(
                    DESCRIPTION_MAX_LENGTH))

    @property
    def metadata(self):
        """
        Возвращает metadata модели DealRequest.

        :return: metadata модели DealRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели DealRequest.

        :param value: metadata модели DealRequest.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

    def validate(self):
        """
        Влидация данных модели DealRequest.
        """
        if self.type is None:
            self.__set_validation_error('Deal type not specified')

        if self.fee_moment is None:
            self.__set_validation_error('Deal fee_moment not specified')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели DealRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

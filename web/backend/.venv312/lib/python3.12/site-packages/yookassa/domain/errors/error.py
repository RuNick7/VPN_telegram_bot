# coding: utf-8
from typing import Dict, Any

from yookassa.domain.common import BaseObject
from yookassa.domain.errors.error_code import ErrorCode


class Error(BaseObject):
    """
    Базовый класс генерируемых объектов Error.
    """  # noqa: E501

    __type = None
    """Тип объекта."""  # noqa: E501

    __id = None
    """Идентификатор ошибки. Используйте его, если возникла необходимость обратиться в техническую поддержку. """  # noqa: E501

    __description = None
    """Подробное описание ошибки."""  # noqa: E501

    __parameter = None
    """Название параметра, из-за которого произошла ошибка."""  # noqa: E501

    __retry_after = None
    """Рекомендуемое количество миллисекунд, спустя которое следует повторить запрос."""  # noqa: E501

    __code = None
    """Код ошибки."""  # noqa: E501

    def __init__(self, data=None):
        super().__init__()
        if data is not None:
            self.from_dict(data)

    @property
    def type(self):
        """Возвращает type модели Error.

        :return: type модели Error.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели Error.

        :param value: type модели Error.
        :type value: str
        """
        self.__type = value

    @property
    def id(self):
        """Возвращает id модели Error.

        :return: id модели Error.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """Устанавливает id модели Error.

        :param value: id модели Error.
        :type value: str
        """
        self.__id = value

    @property
    def description(self):
        """Возвращает description модели Error.

        :return: description модели Error.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """Устанавливает description модели Error.

        :param value: description модели Error.
        :type value: str
        """
        self.__description = value

    @property
    def parameter(self):
        """Возвращает parameter модели Error.

        :return: parameter модели Error.
        :rtype: str
        """
        return self.__parameter

    @parameter.setter
    def parameter(self, value):
        """Устанавливает parameter модели Error.

        :param value: parameter модели Error.
        :type value: str
        """
        self.__parameter = value

    @property
    def retry_after(self):
        """Возвращает retry_after модели Error.

        :return: retry_after модели Error.
        :rtype: int
        """
        return self.__retry_after

    @retry_after.setter
    def retry_after(self, value):
        """Устанавливает retry_after модели Error.

        :param value: retry_after модели Error.
        :type value: int
        """
        self.__retry_after = value

    @property
    def code(self):
        """Возвращает code модели Error.

        :return: code модели Error.
        :rtype: str
        """
        return self.__code

    @code.setter
    def code(self, value):
        """Устанавливает code модели Error.

        :param value: code модели Error.
        :type value: str
        """
        self.__code = value

    def from_dict(self, data: Dict[str, Any]):
        """
        Заполняет объект из словаря.

        :param data: Словарь с данными ошибки.
        :type data: Dict
        """
        if 'id' in data:
            self.id = data['id']
        if 'type' in data:
            self.type = data['type']
        if 'code' in data:
            self.code = data['code']
        if 'description' in data:
            self.description = data['description']
        if 'parameter' in data:
            self.parameter = data['parameter']
        if 'retry_after' in data:
            self.retry_after = data['retry_after']


class InvalidRequestError(Error):
    """Ошибка неверного запроса"""

    def __init__(self, *args, **kwargs):
        super(InvalidRequestError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.INVALID_REQUEST


class InvalidCredentialsError(Error):
    """Ошибка неверных учетных данных"""

    def __init__(self, *args, **kwargs):
        super(InvalidCredentialsError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.INVALID_CREDENTIALS


class ForbiddenError(Error):
    """Ошибка доступа запрещен"""

    def __init__(self, *args, **kwargs):
        super(ForbiddenError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.FORBIDDEN


class NotFoundError(Error):
    """Ошибка не найдено"""

    def __init__(self, *args, **kwargs):
        super(NotFoundError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.NOT_FOUND


class GoneError(Error):
    """Ошибка удаленного ресурса"""

    def __init__(self, *args, **kwargs):
        super(GoneError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.GONE


class TooManyRequestsError(Error):
    """Ошибка слишком многих запросов"""

    def __init__(self, *args, **kwargs):
        super(TooManyRequestsError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.TOO_MANY_REQUESTS


class InternalServerError(Error):
    """Ошибка внутреннего сервера"""

    def __init__(self, *args, **kwargs):
        super(InternalServerError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.INTERNAL_SERVER_ERROR


class CommonError(Error):
    """Общая ошибка"""

    def __init__(self, *args, **kwargs):
        super(CommonError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.ERROR


class UnknownError(Error):
    """Неизвестная ошибка"""

    def __init__(self, *args, **kwargs):
        super(UnknownError, self).__init__(*args, **kwargs)
        if self.type is None:
            self.type = ErrorCode.UNKNOWN


class ErrorFactory(object):
    """
    Фабрика создания объекта Error по типу.
    """  # noqa: E501

    _error_class_map = {
        ErrorCode.INVALID_REQUEST: InvalidRequestError,
        ErrorCode.INVALID_CREDENTIALS: InvalidCredentialsError,
        ErrorCode.FORBIDDEN: ForbiddenError,
        ErrorCode.NOT_FOUND: NotFoundError,
        ErrorCode.GONE: GoneError,
        ErrorCode.TOO_MANY_REQUESTS: TooManyRequestsError,
        ErrorCode.INTERNAL_SERVER_ERROR: InternalServerError,
        ErrorCode.ERROR: CommonError,
    }

    def create(self, data: dict):
        """
        Создание экземпляра ошибки из данных

        :param data: словарь с данными code и description
        :return: Экземпляр объекта ошибки по коду
        :raises ValueError: если отсутствует поле 'code'
        :raises TypeError: если data не словарь
        """
        if not isinstance(data, dict):
            raise TypeError('Parameter "data" should be "dict"')

        if 'code' not in data:
            raise ValueError('Parameter "data" should contain "code" field')

        return self._create_from_data(data)

    def _create_from_data(self, data: dict):
        """
        Создание экземпляра ошибки из данных

        :param data: словарь с данными ошибки
        :return: Экземпляр объекта ошибки
        """
        error_class = self._get_error_class(data['code'])
        return error_class(data)

    def _get_error_class(self, code: str):
        """
        Получение класса ошибки на основе кода

        :param code: код ошибки
        :return: класс ошибки
        """
        return self._error_class_map.get(code, UnknownError)



# -*- coding: utf-8 -*-


class ErrorCode:
    """
    Константы, представляющие коды ошибок. Возможные значения:

    * yookassa.domain.common.ErrorCode.ERROR
    * yookassa.domain.common.ErrorCode.INVALID_REQUEST
    * yookassa.domain.common.ErrorCode.INVALID_CREDENTIALS
    * yookassa.domain.common.ErrorCode.FORBIDDEN
    * yookassa.domain.common.ErrorCode.NOT_FOUND
    * yookassa.domain.common.ErrorCode.GONE
    * yookassa.domain.common.ErrorCode.TOO_MANY_REQUESTS
    * yookassa.domain.common.ErrorCode.INTERNAL_SERVER_ERROR
    * yookassa.domain.common.ErrorCode.UNKNOWN
    """  # noqa: E501

    """
    Список допустимых значений
    """
    ERROR = 'error'
    """Общая ошибка"""

    INVALID_REQUEST = 'invalid_request'
    """Запрос не может быть обработан. Причиной может быть неправильный синтаксис запроса, ошибка в обязательных параметрах запроса, их отсутствие или неподдерживаемый метод."""  # noqa: E501

    INVALID_CREDENTIALS = 'invalid_credentials'
    """В заголовке Authorization указан неверный ключ."""

    FORBIDDEN = 'forbidden'
    """Секретный ключ указан верно, но не хватает прав для совершения операции."""

    NOT_FOUND = 'not_found'
    """Сущность не найдена."""

    GONE = 'gone'
    """Сущность была раньше, но была умышленно удалена и теперь недоступна."""

    TOO_MANY_REQUESTS = 'too_many_requests'
    """Слишком много запросов одновременно отправляется в API. Повторите запрос позже."""

    INTERNAL_SERVER_ERROR = 'internal_server_error'
    """Внутренняя ошибка сервера ЮKassa."""

    UNKNOWN = 'unknown'
    """Для неописанных кодов ошибок."""

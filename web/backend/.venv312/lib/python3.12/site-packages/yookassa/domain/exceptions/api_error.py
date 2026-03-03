# -*- coding: utf-8 -*-
from yookassa.domain.errors.error import ErrorFactory, UnknownError


class ApiError(Exception):
    """
    Неожиданный код ошибки.
    """  # noqa: E501

    __content = None

    __error = None

    HTTP_CODE = 0

    def __init__(self, *args, **kwargs):
        super(ApiError, self).__init__(*args, **kwargs)
        if args[0] is not None:
            error_data = dict(args[0])
            self.__content = error_data

            try:
                factory = ErrorFactory()
                self.__error = factory.create(error_data)
            except (ValueError, TypeError):
                self.__error = UnknownError(error_data)

    @property
    def content(self):
        return self.__content

    @property
    def error(self):
        return self.__error

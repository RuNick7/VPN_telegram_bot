# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class ForbiddenError(ApiError):
    """
    Секретный ключ или OAuth-токен верный, но не хватает прав для совершения операции.
    """  # noqa: E501
    HTTP_CODE = 403


# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class NotFoundError(ApiError):
    """
    Ресурс не найден.
    """  # noqa: E501
    HTTP_CODE = 404

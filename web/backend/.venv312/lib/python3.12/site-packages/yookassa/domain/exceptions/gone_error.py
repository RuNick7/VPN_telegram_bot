# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class GoneError(ApiError):
    """
    Сущность была раньше, но была умышленно удалена и теперь недоступна.
    """  # noqa: E501
    HTTP_CODE = 410

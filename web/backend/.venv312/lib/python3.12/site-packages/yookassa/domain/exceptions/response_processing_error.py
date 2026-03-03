# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class ResponseProcessingError(ApiError):
    """
    Запрос был принят на обработку, но она не завершена.
    """  # noqa: E501
    HTTP_CODE = 202

# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class TooManyRequestsError(ApiError):
    """
    Превышен лимит запросов в единицу времени. Попробуйте снизить интенсивность запросов.
    """  # noqa: E501
    HTTP_CODE = 429

# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class BadRequestError(ApiError):
    """
    Неправильный запрос. Чаще всего этот статус выдается из-за нарушения правил взаимодействия с API.
    """  # noqa: E501
    HTTP_CODE = 400

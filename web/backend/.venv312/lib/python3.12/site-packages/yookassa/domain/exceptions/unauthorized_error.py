# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class UnauthorizedError(ApiError):
    """
    [Basic Auth] Неверный идентификатор вашего аккаунта в ЮKassa или секретный ключ (имя пользователя и пароль при аутентификации).
    [OAuth 2.0] Невалидный OAuth-токен: он некорректный, устарел или его отозвали. Запросите токен заново.
    """  # noqa: E501
    HTTP_CODE = 401

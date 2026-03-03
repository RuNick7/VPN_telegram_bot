# -*- coding: utf-8 -*-
from yookassa.domain.exceptions.api_error import ApiError


class InternalServerError(ApiError):
    """
    Технические неполадки на стороне ЮKassa. Результат обработки запроса неизвестен. Повторите запрос позднее с тем же ключом идемпотентности.
    Рекомендуется повторять запрос с периодичностью один раз в минуту до тех пор, пока ЮKassa не сообщит результат обработки операции.
    """  # noqa: E501
    HTTP_CODE = 500

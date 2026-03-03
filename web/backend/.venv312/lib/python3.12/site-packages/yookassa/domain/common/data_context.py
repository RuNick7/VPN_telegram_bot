# -*- coding: utf-8 -*-
from yookassa.domain.common.context import Context


class DataContext(Context):
    """
    Константы, представляющие контекстные типы данных. Возможные значения:

    * yookassa.domain.common.DataContext.REQUEST
    * yookassa.domain.common.DataContext.RESPONSE
    """  # noqa: E501

    """
    Список допустимых значений
    """
    REQUEST = 'request'
    """Запрос"""
    RESPONSE = 'response'
    """Ответ"""

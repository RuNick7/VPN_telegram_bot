# -*- coding: utf-8 -*-

from yookassa.domain.common import BaseObject
from yookassa.domain.common.data_context import DataContext


class RequestObject(BaseObject):
    """
    Базовый класс для объектов запроса
    """  # noqa: E501
    @staticmethod
    def context():
        """Возвращает контекст запроса"""
        return DataContext.REQUEST

    def validate(self):
        """Валидация данных запроса"""
        pass

# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.common.data_context import DataContext


class ResponseObject(BaseObject):
    """
    Базовый класс для объектов-ответов
    """  # noqa: E501
    @staticmethod
    def context():
        """Возвращает контекст ответа"""
        return DataContext.RESPONSE

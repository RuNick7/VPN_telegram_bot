# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.payment_data.statement import StatementClassMap


class StatementFactory(TypeFactory):
    """
    Фабрика создания объекта Statement по типу.
    """  # noqa: E501

    def __init__(self):
        super(StatementFactory, self).__init__(StatementClassMap())

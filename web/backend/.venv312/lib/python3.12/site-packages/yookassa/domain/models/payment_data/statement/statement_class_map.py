# -*- coding: utf-8 -*-
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.models.payment_data.statement import StatementType
from yookassa.domain.models.payment_data.statement.request.statement_payment_overview import StatementPaymentOverview


class StatementClassMap(DataContext):
    """
    Сопоставление классов Statement по типу.
    """  # noqa: E501

    def __init__(self):
        super(StatementClassMap, self).__init__('request')

    @property
    def request(self):
        return {
            StatementType.PAYMENT_OVERVIEW: StatementPaymentOverview,
        }

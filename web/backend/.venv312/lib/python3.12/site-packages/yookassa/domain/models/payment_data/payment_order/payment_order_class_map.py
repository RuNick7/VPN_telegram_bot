# -*- coding: utf-8 -*-
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.models.payment_data.payment_order.payment_order_type import PaymentOrderType
from yookassa.domain.models.payment_data.payment_order.request.payment_order_utilities import PaymentOrderUtilities


class PaymentOrderClassMap(DataContext):
    """
    Сопоставление классов PaymentOrder по типу.
    """  # noqa: E501

    def __init__(self):
        super(PaymentOrderClassMap, self).__init__('request')

    @property
    def request(self):
        return {
            PaymentOrderType.UTILITIES: PaymentOrderUtilities,
        }

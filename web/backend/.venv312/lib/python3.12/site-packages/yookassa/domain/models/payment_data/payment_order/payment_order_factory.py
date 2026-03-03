# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.payment_data.payment_order.payment_order_class_map import PaymentOrderClassMap


class PaymentOrderFactory(TypeFactory):
    """
    Фабрика создания объекта PaymentOrder по типу.
    """  # noqa: E501

    def __init__(self):
        super(PaymentOrderFactory, self).__init__(PaymentOrderClassMap())

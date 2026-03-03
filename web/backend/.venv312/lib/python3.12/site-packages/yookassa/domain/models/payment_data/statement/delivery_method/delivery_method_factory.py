# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.payment_data.statement.delivery_method.delivery_method_class_map import \
    DeliveryMethodClassMap


class DeliveryMethodFactory(TypeFactory):
    """
    Фабрика создания объекта DeliveryMethod по типу.
    """  # noqa: E501

    def __init__(self):
        super(DeliveryMethodFactory, self).__init__(DeliveryMethodClassMap())

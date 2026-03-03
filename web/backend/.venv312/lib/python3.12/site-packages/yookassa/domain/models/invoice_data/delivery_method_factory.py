# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.invoice_data.delivery_method_class_map import DeliveryMethodClassMap


class DeliveryMethodFactory(TypeFactory):
    """
    Фабрика создания объекта PayoutDestination по типу.
    """  # noqa: E501

    def __init__(self):
        super(DeliveryMethodFactory, self).__init__(DeliveryMethodClassMap())

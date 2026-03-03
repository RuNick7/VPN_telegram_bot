# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.payout_data.payout_destination_class_map import PayoutDestinationClassMap


class PayoutDestinationFactory(TypeFactory):
    """
    Фабрика создания объекта PayoutDestination по типу.
    """  # noqa: E501

    def __init__(self):
        super(PayoutDestinationFactory, self).__init__(PayoutDestinationClassMap())

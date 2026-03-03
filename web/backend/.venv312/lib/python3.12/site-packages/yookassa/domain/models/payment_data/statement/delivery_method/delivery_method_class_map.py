# -*- coding: utf-8 -*-
from yookassa.domain.common import DataContext
from yookassa.domain.models.payment_data.statement.delivery_method.delivery_method_type import DeliveryMethodType
from yookassa.domain.models.payment_data.statement.delivery_method.request.delivery_method_email import \
    DeliveryMethodEmail


class DeliveryMethodClassMap(DataContext):
    """
    Сопоставление классов DeliveryMethod по типу.
    """  # noqa: E501

    def __init__(self):
        super(DeliveryMethodClassMap, self).__init__('request')

    @property
    def request(self):
        return {
            DeliveryMethodType.EMAIL: DeliveryMethodEmail,
        }

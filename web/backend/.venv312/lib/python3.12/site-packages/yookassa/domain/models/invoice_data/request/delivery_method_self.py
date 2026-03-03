# coding: utf-8

from yookassa.domain.common import BaseObject
from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodSelf(DeliveryMethod):
    """Данные для самостоятельной доставки пользователю ссылки на счет."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodSelf, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.SELF:
            self.type = DeliveryMethodType.SELF

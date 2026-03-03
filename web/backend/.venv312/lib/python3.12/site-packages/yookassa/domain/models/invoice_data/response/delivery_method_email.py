# coding: utf-8

from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodEmail(DeliveryMethod):
    """Данные способа отправки счета по электронной почте."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodEmail, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.EMAIL:
            self.type = DeliveryMethodType.EMAIL

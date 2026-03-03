# coding: utf-8

from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodSms(DeliveryMethod):
    """Данные способа отправки счета в смс."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodSms, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.SMS:
            self.type = DeliveryMethodType.SMS

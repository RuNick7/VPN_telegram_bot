# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData


class PaymentDataUnknown(ResponsePaymentData):
    """
    Неизвестный платежный метод.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataUnknown, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.UNKNOWN:
            self.type = PaymentMethodType.UNKNOWN

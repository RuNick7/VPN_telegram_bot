# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataSbp(PaymentData):
    """
    Данные для оплаты через СБП
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataSbp, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBP:
            self.type = PaymentMethodType.SBP

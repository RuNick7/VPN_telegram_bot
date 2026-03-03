# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import ResponsePaymentData


class PaymentDataSberBnpl(ResponsePaymentData):
    """
    Данные для оплаты через сервис «Плати частями».
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataSberBnpl, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBER_BNPL:
            self.type = PaymentMethodType.SBER_BNPL

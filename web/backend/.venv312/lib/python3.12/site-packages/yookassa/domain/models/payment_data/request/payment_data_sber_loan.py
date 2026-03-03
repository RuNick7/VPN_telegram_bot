# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataSberLoan(PaymentData):
    """
    Данные для оплаты в кредит или рассрочку от СберБанка.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataSberLoan, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBER_LOAN:
            self.type = PaymentMethodType.SBER_LOAN

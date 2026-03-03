# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataYooMoneyWallet(PaymentData):
    """
    Данные для проведения оплаты из кошелька ЮMoney.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataYooMoneyWallet, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.YOO_MONEY:
            self.type = PaymentMethodType.YOO_MONEY

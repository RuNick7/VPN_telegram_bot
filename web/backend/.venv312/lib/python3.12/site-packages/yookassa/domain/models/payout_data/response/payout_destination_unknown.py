# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payout_data.payout_destination import PayoutDestination


class PayoutDestinationUnknown(PayoutDestination):
    """
    Данные для выплаты на неизвестный платежный метод.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PayoutDestinationUnknown, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.UNKNOWN:
            self.type = PaymentMethodType.UNKNOWN

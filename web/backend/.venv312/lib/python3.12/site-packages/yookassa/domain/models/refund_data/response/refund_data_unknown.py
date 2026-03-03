# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.refund_data.refund_data import ResponseRefundData


class RefundDataUnknown(ResponseRefundData):
    """
    Данные для возврата на неизвестный платежный метод.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(RefundDataUnknown, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.UNKNOWN:
            self.type = PaymentMethodType.UNKNOWN

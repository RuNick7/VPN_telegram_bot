# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.refund_data.refund_data import ResponseRefundData


class RefundDataSbp(ResponseRefundData):
    """
    Данные для возврата платежа через СБП (НСПК).
    """  # noqa: E501

    __sbp_operation_id = None
    """Идентификатор операции в СБП (НСПК). Пример: ~`1027088AE4CB48CB81287833347A8777`.  Обязательный параметр для возвратов в статусе ~`succeeded`. В остальных случаях может отсутствовать. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(RefundDataSbp, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBP:
            self.type = PaymentMethodType.SBP

    @property
    def sbp_operation_id(self):
        """
        Возвращает sbp_operation_id модели RefundDataSbp.

        :return: sbp_operation_id модели RefundDataSbp.
        :rtype: str
        """
        return self.__sbp_operation_id

    @sbp_operation_id.setter
    def sbp_operation_id(self, value):
        """
        Устанавливает sbp_operation_id модели RefundDataSbp.

        :param value: sbp_operation_id модели RefundDataSbp.
        :type value: str
        """
        self.__sbp_operation_id = value

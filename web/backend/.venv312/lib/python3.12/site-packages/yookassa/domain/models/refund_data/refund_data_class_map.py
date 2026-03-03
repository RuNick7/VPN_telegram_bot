# -*- coding: utf-8 -*-
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.common.payment_method_type import PaymentMethodType
# requests
from yookassa.domain.models.refund_data.request.refund_data_electronic_certificate import \
    RefundDataElectronicCertificate as RequestRefundDataElectronicCertificate
#responses
from yookassa.domain.models.refund_data.response.refund_data_electronic_certificate import \
    RefundDataElectronicCertificate as ResponseRefundDataElectronicCertificate
from yookassa.domain.models.refund_data.response.refund_data_sbp import \
    RefundDataSbp as ResponseRefundDataSbp
from yookassa.domain.models.refund_data.response.refund_data_unknown import \
    RefundDataUnknown as ResponseRefundDataUnknown


class RefundDataClassMap(DataContext):
    """
    Сопоставление классов RefundData по типу.
    """  # noqa: E501

    def __init__(self):
        super(RefundDataClassMap, self).__init__(('request', 'response'))

    @property
    def request(self):
        return {
            PaymentMethodType.ELECTRONIC_CERTIFICATE: RequestRefundDataElectronicCertificate,
        }

    @property
    def response(self):
        return {
            PaymentMethodType.SBP: ResponseRefundDataSbp,
            PaymentMethodType.ELECTRONIC_CERTIFICATE: ResponseRefundDataElectronicCertificate,
            PaymentMethodType.UNKNOWN: ResponseRefundDataUnknown,
        }

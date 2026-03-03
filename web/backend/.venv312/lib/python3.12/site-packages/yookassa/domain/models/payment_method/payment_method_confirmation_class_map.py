# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.models.payment_method.request.payment_method_confirmation_redirect import \
    PaymentMethodConfirmationRedirect as RequestPaymentMethodConfirmationRedirect
from yookassa.domain.models.payment_method.response.payment_method_confirmation_redirect import \
    PaymentMethodConfirmationRedirect as ResponsePaymentMethodConfirmationRedirect


class PaymentMethodConfirmationClassMap(DataContext):
    """
    Сопоставление классов PaymentMethodConfirmation по типу.
    """  # noqa: E501

    def __init__(self):
        super(PaymentMethodConfirmationClassMap, self).__init__(('request', 'response'))

    @property
    def request(self):
        return {
            ConfirmationType.REDIRECT: RequestPaymentMethodConfirmationRedirect,
        }

    @property
    def response(self):
        return {
            ConfirmationType.REDIRECT: ResponsePaymentMethodConfirmationRedirect,
        }

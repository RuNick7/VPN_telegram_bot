# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.models.payment_method.payment_method_confirmation_class_map import \
    PaymentMethodConfirmationClassMap


class PaymentMethodConfirmationFactory(TypeFactory):
    """
    Фабрика создания объекта PaymentMethodConfirmation по типу.
    """  # noqa: E501

    def __init__(self):
        super(PaymentMethodConfirmationFactory, self).__init__(PaymentMethodConfirmationClassMap())

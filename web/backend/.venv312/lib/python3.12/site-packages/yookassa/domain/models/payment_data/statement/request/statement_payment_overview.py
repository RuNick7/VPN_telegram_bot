# -*- coding: utf-8 -*-
from yookassa.domain.models.payment_data.statement import StatementType, Statement
from yookassa.domain.models.payment_data.statement.delivery_method.delivery_method import DeliveryMethod
from yookassa.domain.models.payment_data.statement.delivery_method.delivery_method_factory import DeliveryMethodFactory


class StatementPaymentOverview(Statement):
    """Квитанция по платежу. """  # noqa: E501

    __delivery_method = None
    """Данные о выбранном способе доставки справки. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(StatementPaymentOverview, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not StatementType.PAYMENT_OVERVIEW:
            self.type = StatementType.PAYMENT_OVERVIEW

    @property
    def delivery_method(self):
        """Возвращает delivery_method модели StatementPaymentOverview.

        :return: delivery_method модели StatementPaymentOverview.
        :rtype: DeliveryMethod
        """
        return self.__delivery_method

    @delivery_method.setter
    def delivery_method(self, value):
        """Устанавливает delivery_method модели StatementPaymentOverview.

        :param value: delivery_method модели StatementPaymentOverview.
        :type value: DeliveryMethod
        """
        if isinstance(value, dict):
            self.__delivery_method = DeliveryMethodFactory().create(value, self.context())
        elif isinstance(value, DeliveryMethod):
            self.__delivery_method = value
        else:
            raise TypeError('Invalid delivery_method data type in StatementPaymentOverview.delivery_method')

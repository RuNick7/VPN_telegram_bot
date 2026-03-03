# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PaymentOrder(BaseObject):
    """Платежное поручение — распоряжение на перевод банку для оплаты жилищно-коммунальных услуг (ЖКУ), сведения о платеже для регистрации в ГИС ЖКХ.  Необходимо передавать при %[оплате ЖКУ](/developers/payment-acceptance/scenario-extensions/utility-payments). """  # noqa: E501

    __type = None
    """Код вида платежного поручения."""  # noqa: E501

    @property
    def type(self):
        """Возвращает type модели PaymentOrder.

        :return: type модели PaymentOrder.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели PaymentOrder.

        :param value: type модели PaymentOrder.
        :type value: str
        """
        self.__type = value



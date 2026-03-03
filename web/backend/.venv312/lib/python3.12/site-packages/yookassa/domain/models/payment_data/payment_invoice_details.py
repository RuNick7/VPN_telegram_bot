# coding: utf-8

from yookassa.domain.common import BaseObject


class PaymentInvoiceDetails(BaseObject):
    """Данные о выставленном счете, в рамках которого проведен платеж."""  # noqa: E501

    __id = None
    """Идентификатор счета в ЮКасса."""  # noqa: E501

    @property
    def id(self):
        """Возвращает id модели PaymentInvoiceDetails.

        :return: id модели PaymentInvoiceDetails.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """Устанавливает id модели PaymentInvoiceDetails.

        :param value: id модели PaymentInvoiceDetails.
        :type value: str
        """
        self.__id = value

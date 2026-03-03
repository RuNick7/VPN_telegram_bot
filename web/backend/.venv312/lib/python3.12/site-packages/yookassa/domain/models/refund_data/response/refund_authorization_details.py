# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class RefundAuthorizationDetails(BaseObject):
    """Данные об авторизации возврата. Присутствуют только для возвратов платежей, совершенных этими способами оплаты: банковская карта, Mir Pay. """  # noqa: E501

    __rrn = None
    """Retrieval Reference Number — идентификатор банковской транзакции. """  # noqa: E501

    @property
    def rrn(self):
        """Возвращает rrn модели RefundAuthorizationDetails.

        :return: rrn модели RefundAuthorizationDetails.
        :rtype: str
        """
        return self.__rrn

    @rrn.setter
    def rrn(self, value):
        """Устанавливает rrn модели RefundAuthorizationDetails.

        :param value: rrn модели RefundAuthorizationDetails.
        :type value: str
        """
        self.__rrn = value



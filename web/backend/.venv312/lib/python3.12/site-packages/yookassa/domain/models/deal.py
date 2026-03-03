# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models import Settlement


class PaymentDealInfo(BaseObject):
    """
    Сделка, в рамках которой нужно провести платеж.
    """  # noqa: E501

    __id = None
    """Идентификатор сделки."""  # noqa: E501

    __settlements = []
    """Данные о распределении денег."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PaymentDealInfo.

        :return: id модели PaymentDealInfo.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PaymentDealInfo.

        :param value: id модели PaymentDealInfo.
        :type value: str
        """
        self.__id = value

    @property
    def settlements(self):
        """
        Возвращает settlements модели PaymentDealInfo.

        :return: settlements модели PaymentDealInfo.
        :rtype: list[Settlement]
        """
        return self.__settlements

    @settlements.setter
    def settlements(self, value):
        """
        Устанавливает settlements модели PaymentDealInfo.

        :param value: settlements модели PaymentDealInfo.
        :type value: list[Settlement]
        """
        if isinstance(value, list):
            settlements = []
            for item in value:
                if isinstance(item, dict):
                    settlements.append(Settlement(item))
                elif isinstance(item, Settlement):
                    settlements.append(item)
                else:
                    raise TypeError('Invalid item type in deal.settlements')

            self.__settlements = settlements
        elif value is None:
            self.__settlements = []
        else:
            raise TypeError('Invalid settlements value type in PaymentDealInfo')


class PayoutDealInfo(BaseObject):
    """
    Сделка, в рамках которой нужно провести выплату. Необходимо передавать, если вы проводите %[Безопасную сделку](/developers/solutions-for-platforms/safe-deal/basics)
    """  # noqa: E501

    __id = None
    """Идентификатор сделки."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PayoutDealInfo.

        :return: id модели PayoutDealInfo.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PayoutDealInfo.

        :param value: id модели PayoutDealInfo.
        :type value: str
        """
        self.__id = value


class RefundDealInfo(BaseObject):
    """
    Данные о сделке, в составе которой проходит возврат. Присутствует, если вы проводите %[Безопасную сделку](/developers/solutions-for-platforms/safe-deal/basics).
    """  # noqa: E501

    __id = None
    """Идентификатор сделки."""  # noqa: E501

    __refund_settlements = []
    """Данные о распределении денег."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели RefundDealInfo.

        :return: id модели RefundDealInfo.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели RefundDealInfo.

        :param value: id модели RefundDealInfo.
        :type value: str
        """
        self.__id = value

    @property
    def refund_settlements(self):
        """
        Возвращает refund_settlements модели RefundDealInfo.

        :return: refund_settlements модели RefundDealInfo.
        :rtype: list[Settlement]
        """
        return self.__refund_settlements

    @refund_settlements.setter
    def refund_settlements(self, value):
        """
        Устанавливает refund_settlements модели RefundDealInfo.

        :param value: refund_settlements модели RefundDealInfo.
        :type value: list[Settlement]
        """
        if isinstance(value, list):
            settlements = []
            for item in value:
                if isinstance(item, dict):
                    settlements.append(Settlement(item))
                elif isinstance(item, Settlement):
                    settlements.append(item)
                else:
                    raise TypeError('Invalid item type in deal.refund_settlements')

            self.__refund_settlements = settlements
        elif value is None:
            self.__refund_settlements = []
        else:
            raise TypeError('Invalid refund_settlements value type in RefundDealInfo')


class RefundDealData(BaseObject):
    """
    Данные о сделке, в составе которой проходит возврат. Необходимо передавать, если вы проводите %[Безопасную сделку](/developers/solutions-for-platforms/safe-deal/basics).
    """  # noqa: E501

    __refund_settlements = []
    """Данные о распределении денег."""  # noqa: E501

    @property
    def refund_settlements(self):
        """
        Возвращает refund_settlements модели RefundDealData.

        :return: refund_settlements модели RefundDealData.
        :rtype: list[Settlement]
        """
        return self.__refund_settlements

    @refund_settlements.setter
    def refund_settlements(self, value):
        """
        Устанавливает refund_settlements модели RefundDealData.

        :param value: refund_settlements модели RefundDealData.
        :type value: list[Settlement]
        """
        if isinstance(value, list):
            settlements = []
            for item in value:
                if isinstance(item, dict):
                    settlements.append(Settlement(item))
                elif isinstance(item, Settlement):
                    settlements.append(item)
                else:
                    raise TypeError('Invalid item type in deal.refund_settlements')

            self.__refund_settlements = settlements
        elif value is None:
            self.__refund_settlements = []
        else:
            raise TypeError('Invalid refund_settlements value type in RefundDealData')


class DealType:
    """
    Тип сделки.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    SAFE_DEAL = 'safe_deal'
    """Безопасная сделка."""


class DealStatus:
    """
    Статус сделки.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    OPENED = 'opened'
    """Сделка открыта. Можно выполнять платежи, возвраты и выплаты в составе сделки."""
    CLOSED = 'closed'
    """Сделка закрыта. Вознаграждение перечислено продавцу и платформе или оплата возвращена покупателю. Нельзя выполнять платежи, возвраты и выплаты в составе сделки."""


class FeeMoment:
    """
    Момент перечисления вам вознаграждения платформы.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PAYMENT_SUCCEEDED = 'payment_succeeded'
    """Вознаграждение после успешной оплаты."""
    DEAL_CLOSED = 'deal_closed'
    """Вознаграждение при закрытии сделки после успешной выплаты."""

# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import ResponseObject
from yookassa.domain.models.payment_data.response.credit_card import CreditCard
from yookassa.domain.models.payment_method.payment_method_confirmation_factory import PaymentMethodConfirmationFactory
from yookassa.domain.models.payment_method.response.payment_method_holder import PaymentMethodHolder


class PaymentMethodResponse(ResponseObject):
    """Сохраненный способ оплаты."""  # noqa: E501

    __id = None
    """Идентификатор сохраненного способа оплаты."""  # noqa: E501

    __type = None
    """Код способа оплаты. Возможное значение: * ~`bank_card` — банковская карта."""  # noqa: E501

    __card = None
    """Данные банковской карты."""

    __saved = None
    """Признак сохранения способа оплаты для %[автоплатежей](/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).  Возможные значения:   * ~`true` — способ оплаты сохранен для автоплатежей и выплат; * ~`false` — способ оплаты не сохранен. """  # noqa: E501

    __status = None
    """Статус проверки и сохранения способа оплаты."""  # noqa: E501

    __holder = None
    """Данные магазина, для которого сохраняется способ оплаты."""  # noqa: E501

    __title = None
    """Название способа оплаты."""  # noqa: E501

    __confirmation = None
    """Выбранный сценарий подтверждения привязки. Присутствует, когда привязка ожидает подтверждения от пользователя."""  # noqa: E501

    @property
    def id(self):
        """Возвращает id модели PaymentMethodResponse.

        :return: id модели PaymentMethodResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """Устанавливает id модели PaymentMethodResponse.

        :param value: id модели PaymentMethodResponse.
        :type value: str
        """
        self.__id = value

    @property
    def type(self):
        """Возвращает type модели PaymentMethodResponse.

        :return: type модели PaymentMethodResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели PaymentMethodResponse.

        :param value: type модели PaymentMethodResponse.
        :type value: str
        """
        self.__type = value

    @property
    def card(self):
        """Возвращает card модели PaymentMethodResponse.

        :return: card модели PaymentMethodResponse.
        :rtype: CreditCard
        """
        return self.__card

    @card.setter
    def card(self, value):
        """Устанавливает card модели PaymentMethodResponse.

        :param value: card модели PaymentMethodResponse.
        :type value: CreditCard
        """
        self.__card = CreditCard(value)

    @property
    def saved(self):
        """Возвращает saved модели PaymentMethodResponse.

        :return: saved модели PaymentMethodResponse.
        :rtype: bool
        """
        return self.__saved

    @saved.setter
    def saved(self, value):
        """Устанавливает saved модели PaymentMethodResponse.

        :param value: saved модели PaymentMethodResponse.
        :type value: bool
        """
        self.__saved = value

    @property
    def status(self):
        """Возвращает status модели PaymentMethodResponse.

        :return: status модели PaymentMethodResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """Устанавливает status модели PaymentMethodResponse.

        :param value: status модели PaymentMethodResponse.
        :type value: str
        """
        self.__status = value

    @property
    def holder(self):
        """Возвращает holder модели PaymentMethodResponse.

        :return: holder модели PaymentMethodResponse.
        :rtype: PaymentMethodHolder
        """
        return self.__holder

    @holder.setter
    def holder(self, value):
        """Устанавливает holder модели PaymentMethodResponse.

        :param value: holder модели PaymentMethodResponse.
        :type value: PaymentMethodHolder
        """
        self.__holder = PaymentMethodHolder(value)

    @property
    def title(self):
        """Возвращает title модели PaymentMethodResponse.

        :return: title модели PaymentMethodResponse.
        :rtype: str
        """
        return self.__title

    @title.setter
    def title(self, value):
        """Устанавливает title модели PaymentMethodResponse.

        :param value: title модели PaymentMethodResponse.
        :type value: str
        """
        self.__title = value

    @property
    def confirmation(self):
        """Возвращает confirmation модели PaymentMethodResponse.

        :return: confirmation модели PaymentMethodResponse.
        :rtype: ConfirmationResponse
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """Устанавливает confirmation модели PaymentMethodResponse.

        :param value: confirmation модели PaymentMethodResponse.
        :type value: ConfirmationResponse
        """
        self.__confirmation = PaymentMethodConfirmationFactory().create(value, self.context())

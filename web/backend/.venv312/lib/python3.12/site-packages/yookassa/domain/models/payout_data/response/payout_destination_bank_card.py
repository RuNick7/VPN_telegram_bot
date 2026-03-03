# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payout_data.payout_destination import PayoutDestination
from yookassa.domain.models.payout_data.response.credit_card import CreditCard


class PayoutDestinationBankCard(PayoutDestination):
    """
    Данные для выплаты на банковскую карту.
    """  # noqa: E501

    __card = None
    """Данные банковской карты."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PayoutDestinationBankCard, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.BANK_CARD:
            self.type = PaymentMethodType.BANK_CARD

    @property
    def card(self):
        """
        Возвращает card модели PayoutDestinationBankCard.

        :return: card модели PayoutDestinationBankCard.
        :rtype: CreditCard
        """
        return self.__card

    @card.setter
    def card(self, value):
        """
        Устанавливает card модели PayoutDestinationBankCard.

        :param value: card модели PayoutDestinationBankCard.
        :type value: CreditCard
        """
        if isinstance(value, dict):
            self.__card = CreditCard(value)
        elif isinstance(value, CreditCard):
            self.__card = value
        else:
            raise TypeError('Invalid card value type in PayoutDestinationBankCard')


# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payout_data.payout_destination import PayoutDestination


class PayoutDestinationYooMoneyWallet(PayoutDestination):
    """
    Данные для выплаты на кошелек ЮMoney.
    """  # noqa: E501

    __account_number = None
    """Номер кошелька в ЮMoney, с которого была произведена оплата."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PayoutDestinationYooMoneyWallet, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.YOO_MONEY:
            self.type = PaymentMethodType.YOO_MONEY

    @property
    def account_number(self):
        """
        Возвращает account_number модели PayoutDestinationYooMoneyWallet.

        :return: account_number модели PayoutDestinationYooMoneyWallet.
        :rtype: str
        """
        return self.__account_number

    @account_number.setter
    def account_number(self, value):
        """
        Устанавливает account_number модели PayoutDestinationYooMoneyWallet.

        :param value: account_number модели PayoutDestinationYooMoneyWallet.
        :type value: str
        """
        self.__account_number = str(value)

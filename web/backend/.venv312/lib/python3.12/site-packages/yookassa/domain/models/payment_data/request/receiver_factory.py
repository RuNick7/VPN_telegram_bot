# -*- coding: utf-8 -*-
from yookassa.domain.common.type_factory import TypeFactory
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.models.payment_data.request.receiver import ReceiverBankAccount, ReceiverDigitalWallet, \
    ReceiverMobileBalance, ReceiverType


class ReceiverFactory(TypeFactory):
    """
    Фабрика создания объекта Receiver по типу.
    """  # noqa: E501

    def __init__(self):
        super(ReceiverFactory, self).__init__(ReceiverClassMap())


class ReceiverClassMap(DataContext):
    """
    Сопоставление классов Receiver по типу.
    """  # noqa: E501

    def __init__(self):
        super(ReceiverClassMap, self).__init__(('request'))

    @property
    def request(self):
        return {
            ReceiverType.BANK_ACCOUNT: ReceiverBankAccount,
            ReceiverType.DIGITAL_WALLET: ReceiverDigitalWallet,
            ReceiverType.MOBILE_BALANCE: ReceiverMobileBalance,
        }

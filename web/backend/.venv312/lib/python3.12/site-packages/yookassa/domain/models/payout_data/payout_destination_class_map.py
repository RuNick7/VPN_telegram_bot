# -*- coding: utf-8 -*-
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payout_data.request.payout_destination_bank_card import \
    PayoutDestinationBankCard as RequestPayoutDestinationBankCard
from yookassa.domain.models.payout_data.request.payout_destination_yoomoney_wallet import \
    PayoutDestinationYooMoneyWallet as RequestPayoutDestinationYooMoneyWallet
from yookassa.domain.models.payout_data.request.payout_destination_sbp import \
    PayoutDestinationSbp as RequestPayoutDestinationSbp
from yookassa.domain.models.payout_data.response.payout_destination_bank_card import \
    PayoutDestinationBankCard as ResponsePayoutDestinationBankCard
from yookassa.domain.models.payout_data.response.payout_destination_yoomoney_wallet import \
    PayoutDestinationYooMoneyWallet as ResponsePayoutDestinationYooMoneyWallet
from yookassa.domain.models.payout_data.response.payout_destination_sbp import \
    PayoutDestinationSbp as ResponsePayoutDestinationSbp
from yookassa.domain.models.payout_data.response.payout_destination_unknown import \
    PayoutDestinationUnknown as ResponsePayoutDestinationUnknown


class PayoutDestinationClassMap(DataContext):
    """
    Сопоставление классов PayoutDestination по типу.
    """  # noqa: E501

    def __init__(self):
        super(PayoutDestinationClassMap, self).__init__(('request', 'response'))

    @property
    def request(self):
        return {
            PaymentMethodType.BANK_CARD: RequestPayoutDestinationBankCard,
            PaymentMethodType.YOO_MONEY: RequestPayoutDestinationYooMoneyWallet,
            PaymentMethodType.SBP: RequestPayoutDestinationSbp,
        }

    @property
    def response(self):
        return {
            PaymentMethodType.BANK_CARD: ResponsePayoutDestinationBankCard,
            PaymentMethodType.YOO_MONEY: ResponsePayoutDestinationYooMoneyWallet,
            PaymentMethodType.SBP: ResponsePayoutDestinationSbp,
            PaymentMethodType.UNKNOWN: ResponsePayoutDestinationUnknown,
        }

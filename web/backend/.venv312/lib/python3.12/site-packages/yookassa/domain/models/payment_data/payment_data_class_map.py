# -*- coding: utf-8 -*-
from yookassa.domain.common.data_context import DataContext
from yookassa.domain.common.payment_method_type import PaymentMethodType
# requests
from yookassa.domain.models.payment_data.request.payment_data_applepay import \
    PaymentDataApplepay as RequestPaymentDataApplepay
from yookassa.domain.models.payment_data.request.payment_data_b2b_sberbank import \
    PaymentDataB2bSberbank as RequestPaymentDataB2bSberbank
from yookassa.domain.models.payment_data.request.payment_data_bank_card import \
    PaymentDataBankCard as RequestPaymentDataBankCard
from yookassa.domain.models.payment_data.request.payment_data_cash import \
    PaymentDataCash as RequestPaymentDataCash
from yookassa.domain.models.payment_data.request.payment_data_google_pay import \
    PaymentDataGooglePay as RequestPaymentDataGooglePay
from yookassa.domain.models.payment_data.request.payment_data_mobile_balance import \
    PaymentDataMobileBalance as RequestPaymentDataMobileBalance
from yookassa.domain.models.payment_data.request.payment_data_sberbank import \
    PaymentDataSberbank as RequestPaymentDataSberbank
from yookassa.domain.models.payment_data.request.payment_data_tinkoff_bank import \
    PaymentDataTinkoffBank as RequestPaymentDataTinkoffBank
from yookassa.domain.models.payment_data.request.payment_data_yoomoney_wallet import \
    PaymentDataYooMoneyWallet as RequestPaymentDataYooMoneyWallet
from yookassa.domain.models.payment_data.request.payment_data_sbp import \
    PaymentDataSbp as RequestPaymentDataSbp
from yookassa.domain.models.payment_data.request.payment_data_sber_loan import \
    PaymentDataSberLoan as RequestPaymentDataSberLoan
from yookassa.domain.models.payment_data.request.payment_data_electronic_certificate import \
    PaymentDataElectronicCertificate as RequestPaymentDataElectronicCertificate
from yookassa.domain.models.payment_data.request.payment_data_sber_bnpl import \
    PaymentDataSberBnpl as RequestPaymentDataSberBnpl
# responses
from yookassa.domain.models.payment_data.response.payment_data_alfabank import \
    PaymentDataAlfabank as ResponsePaymentDataAlfabank
from yookassa.domain.models.payment_data.response.payment_data_applepay import \
    PaymentDataApplepay as ResponsePaymentDataApplepay
from yookassa.domain.models.payment_data.response.payment_data_b2b_sberbank import \
    PaymentDataB2bSberbank as ResponsePaymentDataB2bSberbank
from yookassa.domain.models.payment_data.response.payment_data_bank_card import \
    PaymentDataBankCard as ResponsePaymentDataBankCard
from yookassa.domain.models.payment_data.response.payment_data_cash import \
    PaymentDataCash as ResponsePaymentDataCash
from yookassa.domain.models.payment_data.response.payment_data_google_pay import \
    PaymentDataGooglePay as ResponsePaymentDataGooglePay
from yookassa.domain.models.payment_data.response.payment_data_installments import \
    PaymentDataInstallments as ResponsePaymentDataInstallments
from yookassa.domain.models.payment_data.response.payment_data_mobile_balance import \
    PaymentDataMobileBalance as ResponsePaymentDataMobileBalance
from yookassa.domain.models.payment_data.response.payment_data_psb import \
    PaymentDataPsb as ResponsePaymentDataPsb
from yookassa.domain.models.payment_data.response.payment_data_qiwi import \
    PaymentDataQiwi as ResponsePaymentDataQiwi
from yookassa.domain.models.payment_data.response.payment_data_sberbank import \
    PaymentDataSberbank as ResponsePaymentDataSberbank
from yookassa.domain.models.payment_data.response.payment_data_tinkoff_bank import \
    PaymentDataTinkoffBank as ResponsePaymentDataTinkoffBank
from yookassa.domain.models.payment_data.response.payment_data_webmoney import \
    PaymentDataWebmoney as ResponsePaymentDataWebmoney
from yookassa.domain.models.payment_data.response.payment_data_wechat import \
    PaymentDataWechat as ResponsePaymentDataWechat
from yookassa.domain.models.payment_data.response.payment_data_yoomoney_wallet import \
    PaymentDataYooMoneyWallet as ResponsePaymentDataYooMoneyWallet
from yookassa.domain.models.payment_data.response.payment_data_sbp import \
    PaymentDataSbp as ResponsePaymentDataSbp
from yookassa.domain.models.payment_data.response.payment_data_sber_loan import \
    PaymentDataSberLoan as ResponsePaymentDataSberLoan
from yookassa.domain.models.payment_data.response.payment_data_electronic_certificate import \
    PaymentDataElectronicCertificate as ResponsePaymentDataElectronicCertificate
from yookassa.domain.models.payment_data.response.payment_data_sber_bnpl import \
    PaymentDataSberBnpl as ResponsePaymentDataSberBnpl
from yookassa.domain.models.payment_data.response.payment_data_unknown import \
    PaymentDataUnknown as ResponsePaymentDataUnknown


class PaymentDataClassMap(DataContext):
    """
    Сопоставление классов PaymentData по типу.
    """  # noqa: E501

    def __init__(self):
        super(PaymentDataClassMap, self).__init__(('request', 'response'))

    @property
    def request(self):
        return {
            PaymentMethodType.BANK_CARD: RequestPaymentDataBankCard,
            PaymentMethodType.CASH: RequestPaymentDataCash,
            PaymentMethodType.MOBILE_BALANCE: RequestPaymentDataMobileBalance,
            PaymentMethodType.SBERBANK: RequestPaymentDataSberbank,
            PaymentMethodType.YOO_MONEY: RequestPaymentDataYooMoneyWallet,
            PaymentMethodType.APPLEPAY: RequestPaymentDataApplepay,
            PaymentMethodType.GOOGLE_PAY: RequestPaymentDataGooglePay,
            PaymentMethodType.B2B_SBERBANK: RequestPaymentDataB2bSberbank,
            PaymentMethodType.TINKOFF_BANK: RequestPaymentDataTinkoffBank,
            PaymentMethodType.SBP: RequestPaymentDataSbp,
            PaymentMethodType.SBER_LOAN: RequestPaymentDataSberLoan,
            PaymentMethodType.ELECTRONIC_CERTIFICATE: RequestPaymentDataElectronicCertificate,
            PaymentMethodType.SBER_BNPL: RequestPaymentDataSberBnpl,
        }

    @property
    def response(self):
        return {
            PaymentMethodType.ALFABANK: ResponsePaymentDataAlfabank,
            PaymentMethodType.BANK_CARD: ResponsePaymentDataBankCard,
            PaymentMethodType.CASH: ResponsePaymentDataCash,
            PaymentMethodType.MOBILE_BALANCE: ResponsePaymentDataMobileBalance,
            PaymentMethodType.SBERBANK: ResponsePaymentDataSberbank,
            PaymentMethodType.YOO_MONEY: ResponsePaymentDataYooMoneyWallet,
            PaymentMethodType.PSB: ResponsePaymentDataPsb,
            PaymentMethodType.QIWI: ResponsePaymentDataQiwi,
            PaymentMethodType.WEBMONEY: ResponsePaymentDataWebmoney,
            PaymentMethodType.APPLEPAY: ResponsePaymentDataApplepay,
            PaymentMethodType.GOOGLE_PAY: ResponsePaymentDataGooglePay,
            PaymentMethodType.INSTALMENTS: ResponsePaymentDataInstallments,
            PaymentMethodType.B2B_SBERBANK: ResponsePaymentDataB2bSberbank,
            PaymentMethodType.TINKOFF_BANK: ResponsePaymentDataTinkoffBank,
            PaymentMethodType.WECHAT: ResponsePaymentDataWechat,
            PaymentMethodType.SBP: ResponsePaymentDataSbp,
            PaymentMethodType.SBER_LOAN: ResponsePaymentDataSberLoan,
            PaymentMethodType.ELECTRONIC_CERTIFICATE: ResponsePaymentDataElectronicCertificate,
            PaymentMethodType.SBER_BNPL: ResponsePaymentDataSberBnpl,
            PaymentMethodType.UNKNOWN: ResponsePaymentDataUnknown,
        }

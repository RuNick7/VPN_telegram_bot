# -*- coding: utf-8 -*-

class PaymentMethodType:
    """
    Константы, представляющие значения payment_method_data. Возможные значения:

    * yoo_money - Платеж из кошелька ЮMoney
    * bank_card - Платеж с произвольной банковской карты
    * sberbank - Платеж СбербанкОнлайн
    * cash - Платеж наличными
    * mobile_balance - Платеж с баланса мобильного телефона
    * psb - ПромсвязьБанк
    * qiwi - Платеж из кошелька Qiwi
    * webmoney - Платеж из кошелька Webmoney
    * alfabank - Платеж через Альфа-Клик
    * apple_pay - Платеж ApplePay
    * google_pay - Платеж Google Pay
    * installments - Заплатить по частям
    * b2b_sberbank - Сбербанк Бизнес Онлайн
    * tinkoff_bank - T-Pay
    * wechat - Оплата через WeChat
    * sbp - Оплата через сервис быстрых платежей
    * sber_loan - Прием оплаты с использованием Кредита от СберБанка
    * electronic_certificate - Прием платежей по электронному сертификату, привязанному к карте «Мир»
    * sber_bnpl - Прием платежей через сервис «Плати частями»
    * unknown - Для неизвестных методов оплаты
    """  # noqa: E501

    """
    Список допустимых значений
    """
    YOO_MONEY = 'yoo_money'
    """Платеж из кошелька ЮMoney"""
    BANK_CARD = 'bank_card'
    """Платеж с произвольной банковской карты"""
    SBERBANK = 'sberbank'
    """Платеж СбербанкОнлайн"""
    CASH = 'cash'
    """Платеж наличными"""
    MOBILE_BALANCE = 'mobile_balance'
    """Платеж с баланса мобильного телефона"""
    PSB = 'psb'
    """ПромсвязьБанк"""
    QIWI = 'qiwi'
    """Платеж из кошелька Qiwi"""
    WEBMONEY = 'webmoney'
    """Платеж из кошелька Webmoney"""
    ALFABANK = 'alfabank'
    """Платеж через Альфа-Клик"""
    APPLEPAY = 'apple_pay'
    """Платеж ApplePay"""
    GOOGLE_PAY = 'google_pay'
    """Платеж Google Pay"""
    INSTALMENTS = 'installments'
    """Заплатить по частям"""
    B2B_SBERBANK = 'b2b_sberbank'
    """Сбербанк Бизнес Онлайн"""
    TINKOFF_BANK = 'tinkoff_bank'
    """T-Pay"""
    WECHAT = 'wechat'
    """Оплата через WeChat"""
    SBP = 'sbp'
    """Оплата через сервис быстрых платежей"""
    SBER_LOAN = 'sber_loan'
    """Прием оплаты с использованием Кредита от СберБанка"""
    ELECTRONIC_CERTIFICATE = 'electronic_certificate'
    """Прием платежей по электронному сертификату, привязанному к карте «Мир»"""
    SBER_BNPL = 'sber_bnpl'
    """Прием платежей через сервис «Плати частями»"""
    UNKNOWN = 'unknown'
    """Для неизвестных методов оплаты"""

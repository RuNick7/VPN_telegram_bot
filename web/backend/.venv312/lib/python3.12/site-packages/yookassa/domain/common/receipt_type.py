# -*- coding: utf-8 -*-


class ReceiptType:
    """
    Константы, представляющие значения типа чеков. Возможные значения:

    * payment - Тип чека: приход
    * refund - Тип чека: возврат
    """  # noqa: E501

    PAYMENT = 'payment'
    """Тип чека: приход"""
    REFUND = 'refund'
    """Тип чека: возврат"""


class ReceiptItemAgentType:
    """
    Константы, представляющие значения типа посредника. Возможные значения:

    * banking_payment_agent - Банковский платежный агент
    * banking_payment_subagent - Банковский платежный субагент
    * payment_agent - Платежный агент
    * payment_subagent - Платежный субагент
    * attorney - Поверенный
    * commissioner - Комиссионер
    * agent - Агент
    """  # noqa: E501

    """
    Список допустимых значений
    """
    BANKING_PAYMENT_AGENT = 'banking_payment_agent'
    """Банковский платежный агент"""
    BANKING_PAYMENT_SUBAGENT = 'banking_payment_subagent'
    """Банковский платежный субагент"""
    PAYMENT_AGENT = 'payment_agent'
    """Платежный агент"""
    PAYMENT_SUBAGENT = 'payment_subagent'
    """Платежный субагент"""
    ATTORNEY = 'attorney'
    """Поверенный"""
    COMMISSIONER = 'commissioner'
    """Комиссионер"""
    AGENT = 'agent'
    """Агент"""

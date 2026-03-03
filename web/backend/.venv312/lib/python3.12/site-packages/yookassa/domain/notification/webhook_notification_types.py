# -*- coding: utf-8 -*-


class WebhookNotificationType:
    """
    Тип уведомления.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    NOTIFICATION = 'notification'
    """Уведомление."""


class WebhookNotificationEventType:
    """
    Тип события.
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PAYMENT_WAITING_FOR_CAPTURE = 'payment.waiting_for_capture'
    """Успешно оплачен покупателем, ожидает подтверждения магазином."""
    PAYMENT_SUCCEEDED = 'payment.succeeded'
    """Успешно оплачен и подтвержден магазином."""
    PAYMENT_CANCELED = 'payment.canceled'
    """Неуспех оплаты или отменен магазином."""
    REFUND_SUCCEEDED = 'refund.succeeded'
    """Успешный возврат."""
    DEAL_CLOSED = 'deal.closed'
    """Сделка перешла в статус closed."""
    PAYOUT_CANCELED = 'payout.canceled'
    """Выплата перешла в статус canceled."""
    PAYOUT_SUCCEEDED = 'payout.succeeded'
    """Выплата перешла в статус succeeded."""

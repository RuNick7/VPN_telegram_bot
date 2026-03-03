# -*- coding: utf-8 -*-
from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payout_data.payout_destination import PayoutDestination


class PayoutDestinationSbp(PayoutDestination):
    """
    Данные для выплаты на счет в банке через систему быстрых платежей.
    """  # noqa: E501

    __phone = None
    """Телефон, к которому привязан счет получателя выплаты в системе участника СБП."""  # noqa: E501

    __bank_id = None
    """Идентификатор выбранного участника СБП — банка или платежного сервиса, подключенного к сервису. Максимум 12 символов. %[Как получить идентификатор участника СБП](/developers/payouts/making-payouts/sbp) """  # noqa: E501

    __recipient_checked = None
    """Проверка получателя выплаты."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PayoutDestinationSbp, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBP:
            self.type = PaymentMethodType.SBP

    @property
    def phone(self):
        """
        Возвращает phone модели PayoutDestinationSbp.

        :return: phone модели PayoutDestinationSbp.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели PayoutDestinationSbp.

        :param value: phone модели PayoutDestinationSbp.
        :type value: str
        """
        self.__phone = value

    @property
    def bank_id(self):
        """
        Возвращает bank_id модели PayoutDestinationSbp.

        :return: bank_id модели PayoutDestinationSbp.
        :rtype: str
        """
        return self.__bank_id

    @bank_id.setter
    def bank_id(self, value):
        """
        Устанавливает bank_id модели PayoutDestinationSbp.

        :param value: bank_id модели PayoutDestinationSbp.
        :type value: str
        """
        self.__bank_id = value

    @property
    def recipient_checked(self):
        """
        Возвращает recipient_checked модели PayoutDestinationSbp.

        :return: recipient_checked модели PayoutDestinationSbp.
        :rtype: str
        """
        return self.__recipient_checked

    @recipient_checked.setter
    def recipient_checked(self, value):
        """
        Устанавливает recipient_checked модели PayoutDestinationSbp.

        :param value: recipient_checked модели PayoutDestinationSbp.
        :type value: str
        """
        self.__recipient_checked = value

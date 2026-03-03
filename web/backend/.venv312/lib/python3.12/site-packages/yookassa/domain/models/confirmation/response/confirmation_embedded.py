# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.confirmation import Confirmation


class ConfirmationEmbedded(Confirmation):
    """
    Сценарий, при котором действия, необходимые для подтверждения платежа, будут зависеть от способа оплаты, который пользователь выберет в виджете ЮKassa.
    Подтверждение от пользователя получит ЮKassa — вам необходимо только встроить виджет к себе на страницу.
    """  # noqa: E501

    __confirmation_token = None
    """Токен для инициализации платежного %[виджета ЮKassa](/developers/payment-acceptance/integration-scenarios/widget/basics). """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationEmbedded, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.EMBEDDED:
            self.type = ConfirmationType.EMBEDDED

    @property
    def confirmation_token(self):
        """
        Возвращает confirmation_token модели ConfirmationEmbedded.

        :return: confirmation_token модели ConfirmationEmbedded.
        :rtype: str
        """
        return self.__confirmation_token

    @confirmation_token.setter
    def confirmation_token(self, value):
        """
        Устанавливает confirmation_token модели ConfirmationEmbedded.

        :param value: confirmation_token модели ConfirmationEmbedded.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__confirmation_token = cast_value

# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.request.confirmation_request import ConfirmationRequest


class ConfirmationEmbedded(ConfirmationRequest):
    """
    Действия, необходимые для подтверждения платежа, будут зависеть от способа оплаты, который пользователь выберет в виджете ЮKassa.
    Подтверждение от пользователя получит ЮKassa — вам необходимо только встроить виджет к себе на страницу.
    """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationEmbedded, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.EMBEDDED:
            self.type = ConfirmationType.EMBEDDED

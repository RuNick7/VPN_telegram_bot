# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.confirmation import Confirmation


class ConfirmationQr(Confirmation):
    """
    Сценарий при котором для подтверждения платежа пользователю необходимо просканировать QR-код.
    От вас требуется сгенерировать QR-код, используя любой доступный инструмент, и отобразить его на странице оплаты.
    """  # noqa: E501

    __confirmation_data = None
    """Данные для генерации QR-кода. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationQr, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.QR:
            self.type = ConfirmationType.QR

    @property
    def confirmation_data(self):
        """
        Возвращает confirmation_data модели ConfirmationQr.

        :return: confirmation_data модели ConfirmationQr.
        :rtype: str
        """
        return self.__confirmation_data

    @confirmation_data.setter
    def confirmation_data(self, value):
        """
        Устанавливает confirmation_data модели ConfirmationQr.

        :param value: confirmation_data модели ConfirmationQr.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__confirmation_data = cast_value
        else:
            raise ValueError('Invalid confirmation_data value')

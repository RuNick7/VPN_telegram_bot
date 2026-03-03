# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.request.confirmation_request import ConfirmationRequest


class ConfirmationQr(ConfirmationRequest):
    """
    Сценарий при котором для подтверждения платежа пользователю необходимо просканировать QR-код.
    От вас требуется сгенерировать QR-код, используя любой доступный инструмент, и отобразить его на странице оплаты.
    """  # noqa: E501

    __return_url = None
    """
    URL, на который вернется пользователь после подтверждения или отмены платежа на веб-странице. Не более 1024 символов.
    """ # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationQr, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.QR:
            self.type = ConfirmationType.QR

    @property
    def return_url(self):
        """
        Возвращает return_url модели ConfirmationQr.

        :return: return_url модели ConfirmationQr.
        :rtype: str
        """
        return self.__return_url

    @return_url.setter
    def return_url(self, value):
        """
        Устанавливает return_url модели ConfirmationQr.

        :param value: return_url модели ConfirmationQr.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__return_url = cast_value
        else:
            raise ValueError('Invalid returnUrl value')

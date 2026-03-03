# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.request.confirmation_request import ConfirmationRequest


class ConfirmationMobileApplication(ConfirmationRequest):
    """
    Сценарий, при котором необходимо совершить действия в мобильном приложении (например, в приложении интернет-банка).
    """  # noqa: E501

    __return_url = None
    """URL или диплинк, на который вернется пользователь после подтверждения или отмены платежа в приложении. Если платеж делали из мобильной версии сайта, передайте URL, если из мобильного приложения — диплинк. Не более 2048 символов."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationMobileApplication, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.MOBILE_APPLICATION:
            self.type = ConfirmationType.MOBILE_APPLICATION

    @property
    def return_url(self):
        """
        Возвращает return_url модели ConfirmationMobileApplication.

        :return: return_url модели ConfirmationMobileApplication.
        :rtype: str
        """
        return self.__return_url

    @return_url.setter
    def return_url(self, value):
        """
        Устанавливает return_url модели ConfirmationMobileApplication.

        :param value: return_url модели ConfirmationMobileApplication.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__return_url = cast_value
        else:
            raise ValueError('Invalid returnUrl value')

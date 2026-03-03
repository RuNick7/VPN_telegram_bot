# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.confirmation import Confirmation


class ConfirmationMobileApplication(Confirmation):
    """
    Сценарий, при котором необходимо совершить действия в мобильном приложении (например, в приложении интернет-банка).
    """  # noqa: E501

    __confirmation_url = None
    """Диплинк на мобильное приложение, в котором пользователь подтверждает платеж."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationMobileApplication, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.MOBILE_APPLICATION:
            self.type = ConfirmationType.MOBILE_APPLICATION

    @property
    def confirmation_url(self):
        """
        Возвращает confirmation_url модели ConfirmationMobileApplication.

        :return: confirmation_url модели ConfirmationMobileApplication.
        :rtype: str
        """
        return self.__confirmation_url

    @confirmation_url.setter
    def confirmation_url(self, value):
        """
        Устанавливает confirmation_url модели ConfirmationMobileApplication.

        :param value: confirmation_url модели ConfirmationMobileApplication.
        :type value: str
        """
        self.__confirmation_url = value

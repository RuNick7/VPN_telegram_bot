# -*- coding: utf-8 -*-
from yookassa.domain.models.self_employed_data.confirmation import SelfEmployedConfirmation, \
    SelfEmployedConfirmationType


class SelfEmployedConfirmationRedirect(SelfEmployedConfirmation):
    """
    Перенаправление пользователя на сайт сервиса Мой налог для выдачи прав ЮMoney.
    """  # noqa: E501

    __confirmation_url = None
    """URL, на который необходимо перенаправить самозанятого для выдачи прав."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(SelfEmployedConfirmationRedirect, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not SelfEmployedConfirmationType.REDIRECT:
            self.type = SelfEmployedConfirmationType.REDIRECT

    @property
    def confirmation_url(self):
        """
        Возвращает confirmation_url модели SelfEmployedConfirmationRedirect.

        :return: confirmation_url модели SelfEmployedConfirmationRedirect.
        :rtype: str
        """
        return self.__confirmation_url

    @confirmation_url.setter
    def confirmation_url(self, value):
        """
        Устанавливает confirmation_url модели SelfEmployedConfirmationRedirect.

        :param value: confirmation_url модели SelfEmployedConfirmationRedirect.
        :type value: str
        """
        self.__confirmation_url = value

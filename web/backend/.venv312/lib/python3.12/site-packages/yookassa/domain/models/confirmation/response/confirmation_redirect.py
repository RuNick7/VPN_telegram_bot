# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.confirmation.confirmation import Confirmation


class ConfirmationRedirect(Confirmation):
    """
    Сценарий, при котором необходимо отправить плательщика на веб-страницу ЮKassa или партнера для подтверждения платежа.
    """  # noqa: E501

    __return_url = None
    """URL, на который вернется пользователь после подтверждения или отмены платежа на веб-странице. Не более 2048 символов."""  # noqa: E501

    __enforce = None
    """Запрос на проведение платежа с аутентификацией по 3-D Secure. Будет работать, если оплату банковской картой вы по умолчанию принимаете без подтверждения платежа пользователем. В остальных случаях аутентификацией по 3-D Secure будет управлять ЮKassa. Если хотите принимать платежи без дополнительного подтверждения пользователем, напишите вашему менеджеру ЮKassa."""  # noqa: E501

    __confirmation_url = None
    """URL на который необходимо перенаправить плательщика для подтверждения оплаты."""   # noqa: E501

    def __init__(self, *args, **kwargs):
        super(ConfirmationRedirect, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.REDIRECT:
            self.type = ConfirmationType.REDIRECT

    @property
    def return_url(self):
        """
        Возвращает return_url модели ConfirmationRedirect.

        :return: return_url модели ConfirmationRedirect.
        :rtype: str
        """
        return self.__return_url

    @return_url.setter
    def return_url(self, value):
        """
        Устанавливает return_url модели ConfirmationRedirect.

        :param value: return_url модели ConfirmationRedirect.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__return_url = cast_value
        else:
            raise ValueError('Invalid returnUrl value')

    @property
    def enforce(self):
        """
        Возвращает enforce модели ConfirmationRedirect.

        :return: enforce модели ConfirmationRedirect.
        :rtype: bool
        """
        return self.__enforce

    @enforce.setter
    def enforce(self, value):
        """
        Устанавливает enforce модели ConfirmationRedirect.

        :param value: enforce модели ConfirmationRedirect.
        :type value: bool
        """
        self.__enforce = bool(value)

    @property
    def confirmation_url(self):
        """
        Возвращает confirmation_url модели ConfirmationRedirect.

        :return: confirmation_url модели ConfirmationRedirect.
        :rtype: str
        """
        return self.__confirmation_url

    @confirmation_url.setter
    def confirmation_url(self, value):
        """
        Устанавливает confirmation_url модели ConfirmationRedirect.

        :param value: confirmation_url модели ConfirmationRedirect.
        :type value: str
        """
        self.__confirmation_url = value

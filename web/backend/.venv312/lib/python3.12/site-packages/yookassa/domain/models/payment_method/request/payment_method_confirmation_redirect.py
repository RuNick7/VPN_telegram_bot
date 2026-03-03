# -*- coding: utf-8 -*-
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.payment_method.payment_method_confirmation import PaymentMethodConfirmation


class PaymentMethodConfirmationRedirect(PaymentMethodConfirmation):
    """
    Сценарий, при котором необходимо отправить плательщика на веб-страницу ЮKassa или партнера для подтверждения платежа.
    """  # noqa: E501

    __return_url = None
    """URL, на который вернется пользователь после подтверждения или отмены платежа на веб-странице. Не более 2048 символов."""  # noqa: E501

    __locale = None
    """Язык интерфейса, писем и смс, которые будет видеть или получать пользователь. Формат соответствует ISO/IEC 15897. Возможные значения: ru_RU, en_US. Регистр важен."""

    __enforce = None
    """Запрос на проведение платежа с аутентификацией по 3-D Secure. Будет работать, если оплату банковской картой вы по умолчанию принимаете без подтверждения платежа пользователем. В остальных случаях аутентификацией по 3-D Secure будет управлять ЮKassa. Если хотите принимать платежи без дополнительного подтверждения пользователем, напишите вашему менеджеру ЮKassa. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentMethodConfirmationRedirect, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not ConfirmationType.REDIRECT:
            self.type = ConfirmationType.REDIRECT

    @property
    def return_url(self):
        """
        Возвращает return_url модели PaymentMethodConfirmationRedirect.

        :return: return_url модели PaymentMethodConfirmationRedirect.
        :rtype: str
        """
        return self.__return_url

    @return_url.setter
    def return_url(self, value):
        """
        Устанавливает return_url модели PaymentMethodConfirmationRedirect.

        :param value: return_url модели PaymentMethodConfirmationRedirect.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__return_url = cast_value
        else:
            raise ValueError('Invalid returnUrl value')

    @property
    def locale(self):
        """Возвращает locale модели PaymentMethodConfirmationRedirect.

        :return: locale модели PaymentMethodConfirmationRedirect.
        :rtype: str
        """
        return self.__locale

    @locale.setter
    def locale(self, value):
        """Устанавливает locale модели PaymentMethodConfirmationRedirect.

        :param value: locale модели PaymentMethodConfirmationRedirect.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__locale = cast_value
        else:
            raise ValueError('Invalid locale value')

    @property
    def enforce(self):
        """
        Возвращает enforce модели PaymentMethodConfirmationRedirect.

        :return: enforce модели PaymentMethodConfirmationRedirect.
        :rtype: bool
        """
        return self.__enforce

    @enforce.setter
    def enforce(self, value):
        """
        Устанавливает enforce модели PaymentMethodConfirmationRedirect.

        :param value: enforce модели PaymentMethodConfirmationRedirect.
        :type value: bool
        """
        self.__enforce = bool(value)

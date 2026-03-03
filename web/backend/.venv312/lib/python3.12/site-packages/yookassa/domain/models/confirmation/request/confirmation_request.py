# -*- coding: utf-8 -*-
from yookassa.domain.models.confirmation.confirmation import Confirmation


class ConfirmationRequest(Confirmation):
    """
    Данные, необходимые для инициирования выбранного сценария подтверждения платежа пользователем.
    Подробнее о [сценариях подтверждения](/developers/payment-acceptance/getting-started/payment-process#user-confirmation).
    """  # noqa: E501

    __locale = None
    """Язык интерфейса, писем и смс, которые будет видеть или получать пользователь""" # noqa: E501

    @property
    def locale(self):
        """
        Возвращает locale модели ConfirmationRequest.

        :return: locale модели ConfirmationRequest.
        :rtype: Locale
        """
        return self.__locale

    @locale.setter
    def locale(self, value):
        """
        Устанавливает locale модели ConfirmationRequest.

        :param value: locale модели ConfirmationRequest.
        :type value: Locale
        """
        self.__locale = str(value)

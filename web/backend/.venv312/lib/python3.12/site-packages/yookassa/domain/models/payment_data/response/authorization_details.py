# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject


class AuthorizationDetails(BaseObject):
    """Данные об авторизации платежа при оплате банковской картой. Присутствуют только для этих способов оплаты: банковская карта, Mir Pay, SberPay, T-Pay. """  # noqa: E501

    __rrn = None
    """Retrieval Reference Number — уникальный идентификатор транзакции в системе эмитента."""  # noqa: E501

    __auth_code = None
    """Код авторизации. Выдается эмитентом и подтверждает проведение авторизации."""  # noqa: E501

    __three_d_secure = None
    """Данные о прохождении пользователем аутентификации по 3‑D Secure."""  # noqa: E501

    @property
    def rrn(self):
        """
        Возвращает rrn модели AuthorizationDetails.

        :return: rrn модели AuthorizationDetails.
        :rtype: str
        """
        return self.__rrn

    @rrn.setter
    def rrn(self, value):
        """
        Устанавливает rrn модели AuthorizationDetails.

        :param value: rrn модели AuthorizationDetails.
        :type value: str
        """
        self.__rrn = str(value)

    @property
    def auth_code(self):
        """
        Возвращает auth_code модели AuthorizationDetails.

        :return: auth_code модели AuthorizationDetails.
        :rtype: str
        """
        return self.__auth_code

    @auth_code.setter
    def auth_code(self, value):
        """
        Устанавливает auth_code модели AuthorizationDetails.

        :param value: auth_code модели AuthorizationDetails.
        :type value: str
        """
        self.__auth_code = str(value)

    @property
    def three_d_secure(self):
        """
        Возвращает three_d_secure модели AuthorizationDetails.

        :return: three_d_secure модели AuthorizationDetails.
        :rtype: ThreeDSecure
        """
        return self.__three_d_secure

    @three_d_secure.setter
    def three_d_secure(self, value):
        """
        Устанавливает three_d_secure модели AuthorizationDetails.

        :param value: three_d_secure модели AuthorizationDetails.
        :type value: ThreeDSecure
        """
        if isinstance(value, dict):
            self.__three_d_secure = ThreeDSecure(value)
        elif isinstance(value, ThreeDSecure):
            self.__three_d_secure = value
        else:
            raise TypeError('Invalid three_d_secure value type')


class ThreeDSecure(BaseObject):
    """
    Данные о прохождении пользователем аутентификации по 3‑D Secure для подтверждения платежа.
    """  # noqa: E501

    __applied = None
    """Отображение пользователю формы для прохождения аутентификации по 3‑D Secure. Возможные значения:  * ~`true` — ЮKassa отобразила пользователю форму, чтобы он мог пройти аутентификацию по 3‑D Secure; * ~`false` — платеж проходил без аутентификации по 3‑D Secure. """  # noqa: E501

    @property
    def applied(self):
        """
        Возвращает applied модели ThreeDSecure.

        :return: applied модели ThreeDSecure.
        :rtype: bool
        """
        return self.__applied

    @applied.setter
    def applied(self, value):
        """
        Устанавливает applied модели ThreeDSecure.

        :param value: applied модели ThreeDSecure.
        :type value: bool
        """
        self.__applied = bool(value)

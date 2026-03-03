# coding: utf-8

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount
from yookassa.domain.models.settings import FiscalizationData


class Me(BaseObject):
    """
    Объект настроек магазина или шлюза (Me) — актуальная информация о настройках магазина или шлюза.
    """  # noqa: E501

    __account_id = None
    """Идентификатор магазина или шлюза."""

    __status = None
    """Статус магазина или шлюза. Возможные значения:  * ~`enabled` — подключен к ЮKassa, может проводить платежи или выплаты; * ~`disabled` — не может проводить платежи или выплаты (еще не подключен, закрыт или временно не работает). """  # noqa: E501

    __test = None
    """Это тестовый магазин или шлюз. """  # noqa: E501

    __fiscalization = None
    """Настройки магазина для отправки чеков в налоговую."""

    __fiscalization_enabled = None
    """Устаревший параметр, который раньше использовался для определения настроек отправки чеков в налоговую. Сохранен для поддержки обратной совместимости, в новых версиях API может быть удален.  Используйте объект ~`fiscalization`, чтобы определить, какие у магазина настройки отправки чеков. """  # noqa: E501

    __payment_methods = None
    """Список %[способов оплаты](/developers/payment-acceptance/getting-started/payment-methods#all), доступных магазину. Присутствует, если вы запрашивали настройки магазина. """  # noqa: E501

    __itn = None
    """ИНН магазина (10 или 12 цифр). Присутствует, если вы запрашивали настройки магазина."""

    __payout_methods = None
    """Список способов получения выплат, доступных шлюзу. Возможные значения:  * ~`bank_card` — выплаты на банковские карты; * ~`yoo_money` — выплаты на кошельки ЮMoney; * ~`sbp` — выплаты через СБП.  Присутствует, если вы запрашивали настройки шлюза. """  # noqa: E501

    __name = None
    """Название шлюза, которое отображается в личном кабинете ЮKassa. Присутствует, если вы запрашивали настройки шлюза."""  # noqa: E501

    __payout_balance = None
    """Баланс вашего шлюза. Присутствует, если вы запрашивали настройки шлюза."""

    @property
    def account_id(self):
        """
        Возвращает account_id модели Me.

        :return: account_id модели Me.
        :rtype: str
        """
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        """
        Устанавливает account_id модели Me.

        :param value: account_id модели Me.
        :type value: str
        """
        self.__account_id = value

    @property
    def status(self):
        """
        Возвращает status модели Me.

        :return: status модели Me.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели Me.

        :param value: status модели Me.
        :type value: str
        """
        self.__status = value

    @property
    def test(self):
        """
        Возвращает test модели Me.

        :return: test модели Me.
        :rtype: bool
        """
        return self.__test

    @test.setter
    def test(self, value):
        """
        Устанавливает test модели Me.

        :param value: test модели Me.
        :type value: bool
        """
        self.__test = value

    @property
    def fiscalization(self):
        """
        Возвращает fiscalization модели Me.

        :return: fiscalization модели Me.
        :rtype: FiscalizationData
        """
        return self.__fiscalization

    @fiscalization.setter
    def fiscalization(self, value):
        """
        Устанавливает fiscalization модели Me.

        :param value: fiscalization модели Me.
        :type value: FiscalizationData
        """
        if isinstance(value, dict):
            self.__fiscalization = FiscalizationData(value)

    @property
    def fiscalization_enabled(self):
        """
        Возвращает fiscalization_enabled модели Me.

        :return: fiscalization_enabled модели Me.
        :rtype: bool
        """
        return self.__fiscalization_enabled

    @fiscalization_enabled.setter
    def fiscalization_enabled(self, value):
        """
        Устанавливает fiscalization_enabled модели Me.

        :param value: fiscalization_enabled модели Me.
        :type value: bool
        """
        self.__fiscalization_enabled = value

    @property
    def payment_methods(self):
        """
        Возвращает payment_methods модели Me.

        :return: payment_methods модели Me.
        :rtype: list[str]
        """
        return self.__payment_methods

    @payment_methods.setter
    def payment_methods(self, value):
        """
        Устанавливает payment_methods модели Me.

        :param value: payment_methods модели Me.
        :type value: list[str]
        """
        self.__payment_methods = value

    @property
    def itn(self):
        """
        Возвращает itn модели Me.

        :return: itn модели Me.
        :rtype: str
        """
        return self.__itn

    @itn.setter
    def itn(self, value):
        """
        Устанавливает itn модели Me.

        :param value: itn модели Me.
        :type value: str
        """
        self.__itn = value

    @property
    def payout_methods(self):
        """
        Возвращает payout_methods модели Me.

        :return: payout_methods модели Me.
        :rtype: list[str]
        """
        return self.__payout_methods

    @payout_methods.setter
    def payout_methods(self, value):
        """
        Устанавливает payout_methods модели Me.

        :param value: payout_methods модели Me.
        :type value: list[str]
        """
        self.__payout_methods = value

    @property
    def name(self):
        """
        Возвращает name модели Me.

        :return: name модели Me.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Устанавливает name модели Me.

        :param value: name модели Me.
        :type value: str
        """
        self.__name = value

    @property
    def payout_balance(self):
        """
        Возвращает payout_balance модели Me.

        :return: payout_balance модели Me.
        :rtype: Amount
        """
        return self.__payout_balance

    @payout_balance.setter
    def payout_balance(self, value):
        """
        Устанавливает payout_balance модели Me.

        :param value: payout_balance модели Me.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__payout_balance = Amount(value)

# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class IncomeReceipt(BaseObject):
    """
    Данные чека, зарегистрированного в ФНС. Устаревший параметр. Раньше возвращался при проведении выплат самозанятым. Сейчас функциональность недоступна. Параметр сохранен для поддержки обратной совместимости, в новых версиях API может быть удален.
    """  # noqa: E501

    __service_name = None
    """Описание услуги, оказанной получателем выплаты. Не более 50 символов."""  # noqa: E501

    __npd_receipt_id = None
    """Идентификатор чека в сервисе. Пример: ~`208jd98zqe` """  # noqa: E501

    __url = None
    """Ссылка на зарегистрированный чек. Пример: ~`https://www.nalog.gov.ru/api/v1/receipt/<Идентификатор чека>/print` """  # noqa: E501

    __amount = None
    """Сумма, указанная в чеке. Присутствует, если в запросе передавалась сумма для печати в чеке."""  # noqa: E501

    @property
    def service_name(self):
        """
        Возвращает service_name модели IncomeReceipt.

        :return: service_name модели IncomeReceipt.
        :rtype: str
        """
        return self.__service_name

    @service_name.setter
    def service_name(self, value):
        """
        Устанавливает service_name модели IncomeReceipt.

        :param value: service_name модели IncomeReceipt.
        :type value: str
        """
        self.__service_name = value

    @property
    def npd_receipt_id(self):
        """
        Возвращает npd_receipt_id модели IncomeReceipt.

        :return: npd_receipt_id модели IncomeReceipt.
        :rtype: str
        """
        return self.__npd_receipt_id

    @npd_receipt_id.setter
    def npd_receipt_id(self, value):
        """
        Устанавливает npd_receipt_id модели IncomeReceipt.

        :param value: npd_receipt_id модели IncomeReceipt.
        :type value: str
        """
        self.__npd_receipt_id = value

    @property
    def url(self):
        """
        Возвращает url модели IncomeReceipt.

        :return: url модели IncomeReceipt.
        :rtype: str
        """
        return self.__url

    @url.setter
    def url(self, value):
        """
        Устанавливает url модели IncomeReceipt.

        :param value: url модели IncomeReceipt.
        :type value: str
        """
        self.__url = value

    @property
    def amount(self):
        """
        Возвращает amount модели IncomeReceipt.

        :return: amount модели IncomeReceipt.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели IncomeReceipt.

        :param value: amount модели IncomeReceipt.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount data type in IncomeReceipt.amount')

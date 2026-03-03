# -*- coding: utf-8 -*-

from yookassa.domain.common import BaseObject


class ReceiptItemSupplier(BaseObject):
    """
    Информация о поставщике товара или услуги (тег в 54 ФЗ — 1224). Можно передавать, если вы отправляете данные для формирования чека по сценарию %[Сначала платеж, потом чек](/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment).
    """  # noqa: E501

    __name = None
    """Наименование поставщика (тег в 54 ФЗ — 1225). Параметр предусмотрен форматом фискальных документов (ФФД) и является обязательным, начиная с версии 1.1."""  # noqa: E501

    __inn = None
    """ИНН пользователя (10 или 12 цифр)."""  # noqa: E501

    __phone = None
    """Телефон пользователя. Указывается в формате ITU-T E.164."""  # noqa: E501

    @property
    def name(self):
        """
        Возвращает name модели ReceiptItemSupplier.

        :return: name модели ReceiptItemSupplier.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Устанавливает name модели ReceiptItemSupplier.

        :param value: name модели ReceiptItemSupplier.
        :type value: str
        """
        self.__name = str(value)

    @property
    def inn(self):
        """
        Возвращает inn модели ReceiptItemSupplier.

        :return: inn модели ReceiptItemSupplier.
        :rtype: str
        """
        return self.__inn

    @inn.setter
    def inn(self, value):
        """
        Устанавливает inn модели ReceiptItemSupplier.

        :param value: inn модели ReceiptItemSupplier.
        :type value: str
        """
        self.__inn = str(value)

    @property
    def phone(self):
        """
        Возвращает phone модели ReceiptItemSupplier.

        :return: phone модели ReceiptItemSupplier.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели ReceiptItemSupplier.

        :param value: phone модели ReceiptItemSupplier.
        :type value: str
        """
        self.__phone = str(value)


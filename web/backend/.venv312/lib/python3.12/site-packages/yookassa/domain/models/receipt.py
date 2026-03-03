# -*- coding: utf-8 -*-
from yookassa.domain.common import BaseObject
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.operational_details import OperationalDetails
from yookassa.domain.models.receipt_data.receipt_customer import ReceiptCustomer
from yookassa.domain.models.receipt_data.receipt_item import ReceiptItem


class Receipt(BaseObject):
    """
    Объект чека (Receipt) — актуальная информация о чеке.
    """  # noqa: E501

    __customer = None
    """Информация о пользователе."""  # noqa: E501

    __items = []
    """Список товаров в заказе. Для чеков по 54-ФЗ: если используете Чеки от ЮKassa, можно передать максимум 80товаров, если используете стороннюю онлайн-кассу, максимум 100 товаров."""  # noqa: E501

    __internet = None
    """Признак проведения платежа в интернете (тег в 54 ФЗ — 1125) — указывает на оплату через интернет.  Возможные значения: * ~`true` — оплата прошла онлайн, через интернет (например, на вашем сайте или в приложении); * ~`false` — оплата прошла офлайн, при личном взаимодействии (например, в торговой точке или при встрече с курьером). По умолчанию ~`true`. Если вы принимаете платежи офлайн, передайте в запросе значение ~`false`. """  # noqa: E501

    __timezone = None
    """Номер часовой зоны для адреса, по которому вы принимаете платежи (тег в 54 ФЗ — 1011).  Указывается, только если в чеке есть товары, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`). """  # noqa: E501

    __tax_system_code = None
    """Система налогообложения магазина (тег в 54 ФЗ — 1055).  Для сторонних онлайн-касс: обязательный параметр, если вы используете онлайн-кассу Атол Онлайн, обновленную до ФФД 1.2, или у вас несколько систем налогообложения, в остальных случаях не передается. %[Перечень возможных значений](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#tax-systems)  Для Чеков от ЮKassa: параметр передавать не нужно, ЮKassa его проигнорирует. """  # noqa: E501

    __receipt_industry_details = None
    """Отраслевой реквизит чека (тег в 54 ФЗ — 1261). Можно передавать, если используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2. """  # noqa: E501

    __receipt_operational_details = None
    """Операционный реквизит чека (тег в 54 ФЗ — 1270). Можно передавать, если используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2."""  # noqa: E501

    @property
    def customer(self):
        """
        Возвращает customer модели Receipt.

        :return: customer модели Receipt.
        :rtype: ReceiptDataCustomer
        """
        return self.__customer

    @customer.setter
    def customer(self, value):
        """
        Устанавливает customer модели Receipt.

        :param value: customer модели Receipt.
        :type value: ReceiptDataCustomer
        """
        if isinstance(value, dict):
            self.__customer = ReceiptCustomer(value)
        elif isinstance(value, ReceiptCustomer):
            self.__customer = value
        else:
            raise TypeError('Invalid customer value type')

    @property
    def items(self):
        """
        Возвращает items модели Receipt.

        :return: items модели Receipt.
        :rtype: list[ReceiptDataItem]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели Receipt.

        :param value: items модели Receipt.
        :type value: list[ReceiptDataItem]
        """
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append(ReceiptItem(item))
                elif isinstance(item, ReceiptItem):
                    items.append(item)
                else:
                    raise TypeError('Invalid item type in receipt.items')

            self.__items = items
        elif value is None:
            self.__items = []
        else:
            raise TypeError('Invalid items value type in receipt')

    @property
    def internet(self):
        """
        Возвращает internet модели Receipt.

        :return: internet модели Receipt.
        :rtype: bool
        """
        return self.__internet

    @internet.setter
    def internet(self, value):
        """
        Устанавливает internet модели Receipt.

        :param value: internet модели Receipt.
        :type value: bool
        """
        if isinstance(value, bool):
            self.__internet = value
        else:
            raise TypeError('Invalid internet value type in Receipt')

    @property
    def timezone(self):
        """
        Возвращает timezone модели Receipt.

        :return: timezone модели Receipt.
        :rtype: int
        """
        return self.__timezone

    @timezone.setter
    def timezone(self, value):
        """
        Устанавливает timezone модели Receipt.

        :param value: timezone модели Receipt.
        :type value: int
        """
        if value is not None and value > 11:  # noqa: E501
            raise ValueError("Invalid value for `timezone`, must be a value less than or equal to `11`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `timezone`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__timezone = value

    @property
    def tax_system_code(self):
        """
        Возвращает tax_system_code модели Receipt.

        :return: tax_system_code модели Receipt.
        :rtype: str
        """
        return self.__tax_system_code

    @tax_system_code.setter
    def tax_system_code(self, value):
        """
        Устанавливает tax_system_code модели Receipt.

        :param value: email модели Receipt.
        """
        if isinstance(value, int):
            self.__tax_system_code = value
        else:
            raise TypeError('Invalid tax_system_code value type')

    @property
    def email(self):
        """
        Возвращает email модели Receipt.

        :return: email модели Receipt.
        :rtype: str
        """
        return None

    @email.setter
    def email(self, value):
        """
        Устанавливает email модели Receipt.

        :param value: email модели Receipt.
        :type value: str
        """
        if self.__customer is None:
            self.__customer = ReceiptCustomer()
        self.__customer.email = str(value)

    @property
    def phone(self):
        """
        Возвращает tax_system_code модели Receipt.

        :return: tax_system_code модели Receipt.
        :rtype: str
        """
        return None

    @phone.setter
    def phone(self, value):
        """
        Устанавливает tax_system_code модели Receipt.

        :param value: tax_system_code модели Receipt.
        :type value: str
        """
        if self.__customer is None:
            self.__customer = ReceiptCustomer()
        self.__customer.phone = str(value)

    def has_items(self):
        """
        Возвращает флаг установки items модели Receipt.

        :return: has items модели Receipt.
        :rtype: bool
        """
        return bool(self.items)

    @property
    def receipt_industry_details(self):
        """
        Возвращает receipt_industry_details модели Receipt.

        :return: receipt_industry_details модели Receipt.
        :rtype: list[IndustryDetails]
        """
        return self.__receipt_industry_details

    @receipt_industry_details.setter
    def receipt_industry_details(self, value):
        """
        Устанавливает receipt_industry_details модели Receipt.

        :param value: receipt_industry_details модели Receipt.
        :type value: list[IndustryDetails]
        """
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append(IndustryDetails(item))
                elif isinstance(item, IndustryDetails):
                    items.append(item)
                else:
                    raise TypeError('Invalid receipt_industry_details data type in ReceiptData.receipt_industry_details')
            self.__receipt_industry_details = items
        else:
            raise TypeError('Invalid receipt_industry_details value type in ReceiptData')

    @property
    def receipt_operational_details(self):
        """
        Возвращает receipt_operational_details модели Receipt.

        :return: receipt_operational_details модели Receipt.
        :rtype: OperationalDetails
        """
        return self.__receipt_operational_details

    @receipt_operational_details.setter
    def receipt_operational_details(self, value):
        """
        Устанавливает receipt_operational_details модели Receipt.

        :param value: receipt_operational_details модели Receipt.
        :type value: OperationalDetails
        """
        if isinstance(value, dict):
            self.__receipt_operational_details = OperationalDetails(value)
        elif isinstance(value, OperationalDetails):
            self.__receipt_operational_details = value
        else:
            raise TypeError('Invalid receipt_operational_details data type in ReceiptData.receipt_operational_details')

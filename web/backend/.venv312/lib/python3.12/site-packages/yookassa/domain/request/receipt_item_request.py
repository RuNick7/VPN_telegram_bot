# -*- coding: utf-8 -*-
import re
from decimal import Decimal

from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.mark_code_info import MarkCodeInfo
from yookassa.domain.models.receipt_data.mark_quantity import MarkQuantity
from yookassa.domain.models.receipt_data.receipt_item_supplier import ReceiptItemSupplier


class ReceiptItemRequest(BaseObject):
    """
    Объект запроса к API на создание товарной позиции в заказе (для формирования чека).
    """  # noqa: E501

    __description = None
    """Название товара (от 1 до 128 символов). Тег в 54 ФЗ — 1030. """  # noqa: E501

    __amount = None
    """Суммарная стоимость покупаемого товара в копейках/центах."""  # noqa: E501

    __vat_code = None
    """Ставка НДС, число 1-12 (тег в 54 ФЗ — 1199)."""  # noqa: E501

    __quantity = None
    """Количество (тег в 54 ФЗ — 1023)."""  # noqa: E501

    __measure = None
    """Мера количества предмета расчета (тег в 54 ФЗ — 2108)."""  # noqa: E501

    __mark_quantity = None
    """Дробное количество маркированного товара (тег в 54 ФЗ — 1291)."""  # noqa: E501

    __payment_subject = None
    """Признак предмета расчета (тег в 54 ФЗ — 1212)."""  # noqa: E501

    __payment_mode = None
    """Признак способа расчета (тег в 54 ФЗ — 1214)."""  # noqa: E501

    __country_of_origin_code = None
    """Код страны происхождения товара по общероссийскому классификатору стран мира ([OК (MК (ИСО 3166) 004-97) 025-2001](http://docs.cntd.ru/document/842501280)). Тег в 54 ФЗ — 1230. Пример: ~`RU`. <br/>Можно передавать, если используете онлайн-кассу Orange Data, Кит Инвест. """  # noqa: E501

    __customs_declaration_number = None
    """Номер таможенной декларации (от 1 до 32 символов). Тег в 54 ФЗ — 1231. <br/>Можно передавать, если используете онлайн-кассу Orange Data, Кит Инвест. """  # noqa: E501

    __excise = None
    """Сумма акциза товара с учетом копеек (тег в 54 ФЗ — 1229). Десятичное число с точностью до 2 знаков после точки. <br/>Можно передавать, если используете онлайн-кассу Orange Data, Кит Инвест. """  # noqa: E501

    __product_code = None
    """Код товара (тег в 54 ФЗ — 1162) — уникальный номер, который присваивается экземпляру товара при маркировке. <br/>Формат: число в шестнадцатеричном представлении с пробелами. Максимальная длина — 32 байта. Пример: ~`00 00 00 01 00 21 FA 41 00 23 05 41 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 12 00 AB 00`.  Обязательный параметр, если одновременно выполняются эти условия:  * вы используете онлайн-кассу, обновленную до ФФД 1.05; * товар нужно [маркировать](http://docs.cntd.ru/document/902192509). """  # noqa: E501

    __planned_status = None
    """Планируемый статус товара. Тег в 54 ФЗ — 2003. Указывается только для товаров, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`).  Перечень возможных значений:  * [для Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#planned-status) * [для сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#planned-status) """  # noqa: E501

    __mark_code_info = None
    """Код товара (тег в 54 ФЗ — 1163)."""  # noqa: E501

    __mark_mode = None
    """Режим обработки кода маркировки (тег в 54 ФЗ — 2102).  Обязательный параметр, если одновременно выполняются эти условия:  * вы используете Чеки от ЮKassa или онлайн-кассу Атол Онлайн или BusinessRu, обновленную до ФФД 1.2; * товар нужно [маркировать](http://docs.cntd.ru/document/902192509).  Должен принимать значение равное «0». """  # noqa: E501

    __payment_subject_industry_details = None
    """Отраслевой реквизит предмета расчета (тег в 54 ФЗ — 1260). Можно передавать, если используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2. """  # noqa: E501

    __additional_payment_subject_props = None
    """ Дополнительный реквизит предмета расчета (тег в 54 ФЗ — 1191). Не более 64 символов. <br/>Можно передавать, если вы отправляете данные для формирования чека по сценарию %[Сначала платеж, потом чек](/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment) """  # noqa: E501

    __supplier = None
    """Информация о поставщике товара или услуги (тег в 54 ФЗ — 1224)."""  # noqa: E501

    __agent_type = None
    """Тип посредника, реализующего товар или услугу."""  # noqa: E501

    @property
    def description(self):
        """
        Возвращает description модели ReceiptItemRequest.

        :return: description модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели ReceiptItemRequest.

        :param value: description модели ReceiptItemRequest.
        :type value: str
        """
        self.__description = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели ReceiptItemRequest.

        :return: amount модели ReceiptItemRequest.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели ReceiptItemRequest.

        :param value: amount модели ReceiptItemRequest.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def quantity(self):
        """
        Возвращает quantity модели ReceiptItemRequest.

        :return: quantity модели ReceiptItemRequest.
        :rtype: Decimal
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """
        Устанавливает quantity модели ReceiptItemRequest.

        :param value: quantity модели ReceiptItemRequest.
        :type value: Decimal
        """
        self.__quantity = Decimal(str(float(value)))

    @property
    def measure(self):
        """
        Возвращает measure модели ReceiptItemRequest.

        :return: measure модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__measure

    @measure.setter
    def measure(self, value):
        """
        Устанавливает measure модели ReceiptItemRequest.

        :param value: measure модели ReceiptItemRequest.
        :type value: str
        """
        self.__measure = value

    @property
    def mark_quantity(self):
        """
        Возвращает mark_quantity модели ReceiptItemRequest.

        :return: mark_quantity модели ReceiptItemRequest.
        :rtype: MarkQuantity
        """
        return self.__mark_quantity

    @mark_quantity.setter
    def mark_quantity(self, value):
        """
        Устанавливает mark_quantity модели ReceiptItemRequest.

        :param value: mark_quantity модели ReceiptItemRequest.
        :type value: MarkQuantity
        """
        if isinstance(value, dict):
            self.__mark_quantity = MarkQuantity(value)
        elif isinstance(value, MarkQuantity):
            self.__mark_quantity = value
        else:
            raise TypeError('Invalid mark_quantity data type in ReceiptItemRequest.mark_quantity')

    @property
    def vat_code(self):
        """
        Возвращает vat_code модели ReceiptItemRequest.

        :return: vat_code модели ReceiptItemRequest.
        :rtype: int
        """
        return self.__vat_code

    @vat_code.setter
    def vat_code(self, value):
        """
        Устанавливает vat_code модели ReceiptItemRequest.

        :param value: vat_code модели ReceiptItemRequest.
        :type value: int
        """
        self.__vat_code = int(value)

    @property
    def payment_subject(self):
        """
        Возвращает payment_subject модели ReceiptItemRequest.

        :return: payment_subject модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__payment_subject

    @payment_subject.setter
    def payment_subject(self, value):
        """
        Устанавливает payment_subject модели ReceiptItemRequest.

        :param value: payment_subject модели ReceiptItemRequest.
        :type value: str
        """
        self.__payment_subject = str(value)

    @property
    def payment_mode(self):
        """
        Возвращает payment_mode модели ReceiptItemRequest.

        :return: payment_mode модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__payment_mode

    @payment_mode.setter
    def payment_mode(self, value):
        """
        Устанавливает payment_mode модели ReceiptItemRequest.

        :param value: payment_mode модели ReceiptItemRequest.
        :type value: str
        """
        self.__payment_mode = str(value)

    @property
    def country_of_origin_code(self):
        """
        Возвращает country_of_origin_code модели ReceiptItemRequest.

        :return: country_of_origin_code модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__country_of_origin_code

    @country_of_origin_code.setter
    def country_of_origin_code(self, value):
        """
        Устанавливает country_of_origin_code модели ReceiptItemRequest.

        :param value: country_of_origin_code модели ReceiptItemRequest.
        :type value: str
        """
        self.__country_of_origin_code = str(value)

    @property
    def customs_declaration_number(self):
        """
        Возвращает customs_declaration_number модели ReceiptItemRequest.

        :return: customs_declaration_number модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__customs_declaration_number

    @customs_declaration_number.setter
    def customs_declaration_number(self, value):
        """
        Устанавливает customs_declaration_number модели ReceiptItemRequest.

        :param value: customs_declaration_number модели ReceiptItemRequest.
        :type value: str
        """
        self.__customs_declaration_number = str(value)

    @property
    def excise(self):
        """
        Возвращает excise модели ReceiptItemRequest.

        :return: excise модели ReceiptItemRequest.
        :rtype: Decimal
        """
        return self.__excise

    @excise.setter
    def excise(self, value):
        """
        Устанавливает excise модели ReceiptItemRequest.

        :param value: excise модели ReceiptItemRequest.
        :type value: Decimal
        """
        self.__excise = Decimal(str(float(value)))

    @property
    def product_code(self):
        """
        Возвращает product_code модели ReceiptItemRequest.

        :return: product_code модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__product_code

    @product_code.setter
    def product_code(self, value):
        """
        Устанавливает product_code модели ReceiptItemRequest.

        :param value: product_code модели ReceiptItemRequest.
        :type value: str
        """
        self.__product_code = str(value)

    @property
    def planned_status(self):
        """Возвращает planned_status модели ReceiptItemRequest.

        :return: planned_status модели ReceiptItemRequest.
        :rtype: int
        """
        return self.__planned_status

    @planned_status.setter
    def planned_status(self, value):
        """Устанавливает planned_status модели ReceiptItemRequest.

        :param value: planned_status модели ReceiptItemRequest.
        :type value: int
        """
        if value is not None and value > 6:  # noqa: E501
            raise ValueError(
                "Invalid value for `planned_status`, must be a value less than or equal to `6`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError(
                "Invalid value for `planned_status`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__planned_status = int(value)

    @property
    def mark_code_info(self):
        """
        Возвращает mark_code_info модели ReceiptItemRequest.

        :return: mark_code_info модели ReceiptItemRequest.
        :rtype: MarkCodeInfo
        """
        return self.__mark_code_info

    @mark_code_info.setter
    def mark_code_info(self, value):
        """
        Устанавливает mark_code_info модели ReceiptItemRequest.

        :param value: mark_code_info модели ReceiptItemRequest.
        :type value: MarkCodeInfo
        """
        if isinstance(value, dict):
            self.__mark_code_info = MarkCodeInfo(value)
        elif isinstance(value, MarkCodeInfo):
            self.__mark_code_info = value
        else:
            raise TypeError('Invalid mark_code_info data type in ReceiptItemRequest.mark_code_info')

    @property
    def mark_mode(self):
        """
        Возвращает mark_mode модели ReceiptItemRequest.

        :return: mark_mode модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__mark_mode

    @mark_mode.setter
    def mark_mode(self, value):
        """
        Устанавливает mark_mode модели ReceiptItemRequest.

        :param value: mark_mode модели ReceiptItemRequest.
        :type value: str
        """
        if value is not None and not re.search(r'^[0]{1}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `mark_mode`, must be a follow pattern or equal to `/^[0]{1}$/`")  # noqa: E501
        self.__mark_mode = value

    @property
    def payment_subject_industry_details(self):
        """
        Возвращает payment_subject_industry_details модели ReceiptItemRequest.

        :return: payment_subject_industry_details модели ReceiptItemRequest.
        :rtype: list[IndustryDetails]
        """
        return self.__payment_subject_industry_details

    @payment_subject_industry_details.setter
    def payment_subject_industry_details(self, value):
        """
        Устанавливает payment_subject_industry_details модели ReceiptItemRequest.

        :param value: payment_subject_industry_details модели ReceiptItemRequest.
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
                    raise TypeError('Invalid payment_subject_industry_details data type in ReceiptItemRequest.payment_subject_industry_details')
            self.__payment_subject_industry_details = items
        else:
            raise TypeError('Invalid payment_subject_industry_details value type in ReceiptItem')

    @property
    def additional_payment_subject_props(self):
        """
        Возвращает additional_payment_subject_props модели ReceiptItemRequest.

        :return: additional_payment_subject_props модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__additional_payment_subject_props

    @additional_payment_subject_props.setter
    def additional_payment_subject_props(self, value):
        """
        Устанавливает additional_payment_subject_props модели ReceiptItemRequest.

        :param value: additional_payment_subject_props модели ReceiptItemRequest.
        :type value: str
        """
        if value is not None and len(value) > 64:
            raise ValueError("Invalid value for `additional_payment_subject_props`, length must be less than or equal to `64`")  # noqa: E501
        self.__additional_payment_subject_props = value

    @property
    def supplier(self):
        """
        Возвращает supplier модели ReceiptItemRequest.

        :return: supplier модели ReceiptItemRequest.
        :rtype: ReceiptItemSupplier
        """
        return self.__supplier

    @supplier.setter
    def supplier(self, value):
        """
        Устанавливает supplier модели ReceiptItemRequest.

        :param value: supplier модели ReceiptItemRequest.
        :type value: ReceiptItemSupplier
        """
        if isinstance(value, dict):
            self.__supplier = ReceiptItemSupplier(value)
        elif isinstance(value, ReceiptItemSupplier):
            self.__supplier = value
        else:
            raise TypeError('Invalid supplier value type')

    @property
    def agent_type(self):
        """
        Возвращает agent_type модели ReceiptItemRequest.

        :return: agent_type модели ReceiptItemRequest.
        :rtype: str
        """
        return self.__agent_type

    @agent_type.setter
    def agent_type(self, value):
        """
        Устанавливает agent_type модели ReceiptItemRequest.

        :param value: agent_type модели ReceiptItemRequest.
        :type value: str
        """
        self.__agent_type = str(value)

# -*- coding: utf-8 -*-
from decimal import Decimal

from yookassa.domain.common import ResponseObject
from yookassa.domain.models import Amount, ReceiptItemSupplier
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.mark_code_info import MarkCodeInfo
from yookassa.domain.models.receipt_data.mark_quantity import MarkQuantity


class ReceiptItemResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о товарной позиции в заказе.
    """  # noqa: E501

    __description = None
    """Название товара (не более 128 символов). Тег в 54 ФЗ — 1030)."""  # noqa: E501

    __quantity = None
    """Количество товара (тег в 54 ФЗ — 1023). Формат: десятичное число, дробная часть — три знака или больше (количество знаков зависит от `quantity` в запросе). Разделитель дробной части — точка, разделитель тысяч отсутствует. Пример: ~`5.000` """  # noqa: E501

    __amount = None
    """Суммарная стоимость покупаемого товара в копейках/центах."""  # noqa: E501

    __vat_code = None
    """Ставка НДС, число 1-12 (тег в 54 ФЗ — 1199)."""  # noqa: E501

    __payment_subject = None
    """Признак предмета расчета (тег в 54 ФЗ — 1212)."""  # noqa: E501

    __payment_mode = None
    """Признак способа расчета (тег в 54 ФЗ — 1214)."""  # noqa: E501

    __country_of_origin_code = None
    """Код страны происхождения товара по общероссийскому классификатору стран мира ([OК (MК (ИСО 3166) 004-97) 025-2001](http://docs.cntd.ru/document/842501280)). Тег в 54 ФЗ — 1230. Пример: ~`RU`. <br/>Онлайн-кассы, которые поддерживают этот параметр: Orange Data, Кит Инвест. """  # noqa: E501

    __customs_declaration_number = None
    """Номер таможенной декларации (от 1 до 32 символов). Тег в 54 ФЗ — 1231. <br/>Онлайн-кассы, которые поддерживают этот параметр: Orange Data, Кит Инвест. """  # noqa: E501

    __excise = None
    """Сумма акциза товара с учетом копеек (тег в 54 ФЗ — 1229). Десятичное число с точностью до 2 символов после точки. <br/>Онлайн-кассы, которые поддерживают этот параметр: Orange Data, Кит Инвест. """  # noqa: E501

    __supplier = None
    """Информация о поставщике товара или услуги (тег в 54 ФЗ — 1224)."""  # noqa: E501

    __agent_type = None
    """Тип посредника, реализующего товар или услугу."""  # noqa: E501

    __mark_code_info = None
    """Код товара (тег в 54 ФЗ — 1163)."""  # noqa: E501

    __measure = None
    """Мера количества предмета расчета (тег в 54 ФЗ — 2108)."""  # noqa: E501

    __payment_subject_industry_details = None
    """Отраслевой реквизит предмета расчета  (тег в 54 ФЗ — 1260). Обязателен при использовании ФФД 1.2."""  # noqa: E501

    __product_code = None
    """Код товара — уникальный номер, который присваивается экземпляру товара при [маркировке](http://docs.cntd.ru/document/902192509) (тег в 54 ФЗ — 1162). <br/>Формат: число в шестнадцатеричном представлении с пробелами. Максимальная длина — 32 байта. Пример: ~`00 00 00 01 00 21 FA 41 00 23 05 41 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 12 00 AB 00`. <br/>Обязательный параметр, если товар нужно [маркировать](http://docs.cntd.ru/document/557297080). """  # noqa: E501

    __planned_status = None
    """Планируемый статус товара. Тег в 54 ФЗ — 2003. Указывается только для товаров, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`).  Перечень возможных значений:  * [для Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#planned-status) * [для сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#planned-status) """  # noqa: E501

    __mark_mode = None
    """Режим обработки кода маркировки (тег в 54 ФЗ — 2102).  Обязательный параметр, если одновременно выполняются эти условия:  * вы используете Чеки от ЮKassa или онлайн-кассу Атол Онлайн или BusinessRu, обновленную до ФФД 1.2; * товар нужно [маркировать](http://docs.cntd.ru/document/902192509).  Должен принимать значение равное «0». """  # noqa: E501

    __mark_quantity = None
    """Дробное количество маркированного товара (тег в 54 ФЗ — 1291)."""  # noqa: E501

    @property
    def description(self):
        """
        Возвращает description модели ReceiptItemResponse.

        :return: description модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели ReceiptItemResponse.

        :param value: description модели ReceiptItemResponse.
        :type value: str
        """
        self.__description = value

    @property
    def quantity(self):
        """
        Возвращает quantity модели ReceiptItemResponse.

        :return: quantity модели ReceiptItemResponse.
        :rtype: Decimal
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """
        Устанавливает quantity модели ReceiptItemResponse.

        :param value: quantity модели ReceiptItemResponse.
        :type value: Decimal
        """
        self.__quantity = Decimal(str(float(value)))

    @property
    def amount(self):
        """
        Возвращает amount модели ReceiptItemResponse.

        :return: amount модели ReceiptItemResponse.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели ReceiptItemResponse.

        :param value: amount модели ReceiptItemResponse.
        :type value: Amount
        """
        self.__amount = Amount(value)

    @property
    def vat_code(self):
        """
        Возвращает vat_code модели ReceiptItemResponse.

        :return: vat_code модели ReceiptItemResponse.
        :rtype: int
        """
        return self.__vat_code

    @vat_code.setter
    def vat_code(self, value):
        """
        Устанавливает vat_code модели ReceiptItemResponse.

        :param value: vat_code модели ReceiptItemResponse.
        :type value: int
        """
        self.__vat_code = int(value)

    @property
    def payment_subject(self):
        """
        Возвращает payment_subject модели ReceiptItemResponse.

        :return: payment_subject модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__payment_subject

    @payment_subject.setter
    def payment_subject(self, value):
        """
        Устанавливает payment_subject модели ReceiptItemResponse.

        :param value: payment_subject модели ReceiptItemResponse.
        :type value: str
        """
        self.__payment_subject = str(value)

    @property
    def payment_mode(self):
        """
        Возвращает payment_mode модели ReceiptItemResponse.

        :return: payment_mode модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__payment_mode

    @payment_mode.setter
    def payment_mode(self, value):
        """
        Устанавливает payment_mode модели ReceiptItemResponse.

        :param value: payment_mode модели ReceiptItemResponse.
        :type value: str
        """
        self.__payment_mode = str(value)

    @property
    def country_of_origin_code(self):
        """
        Возвращает country_of_origin_code модели ReceiptItemResponse.

        :return: country_of_origin_code модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__country_of_origin_code

    @country_of_origin_code.setter
    def country_of_origin_code(self, value):
        """
        Устанавливает country_of_origin_code модели ReceiptItemResponse.

        :param value: country_of_origin_code модели ReceiptItemResponse.
        :type value: str
        """
        self.__country_of_origin_code = value

    @property
    def customs_declaration_number(self):
        """
        Возвращает customs_declaration_number модели ReceiptItemResponse.

        :return: customs_declaration_number модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__customs_declaration_number

    @customs_declaration_number.setter
    def customs_declaration_number(self, value):
        """
        Устанавливает customs_declaration_number модели ReceiptItemResponse.

        :param value: customs_declaration_number модели ReceiptItemResponse.
        :type value: str
        """
        self.__customs_declaration_number = value

    @property
    def excise(self):
        """
        Возвращает excise модели ReceiptItemResponse.

        :return: excise модели ReceiptItemResponse.
        :rtype: Decimal
        """
        return self.__excise

    @excise.setter
    def excise(self, value):
        """
        Устанавливает excise модели ReceiptItemResponse.

        :param value: excise модели ReceiptItemResponse.
        :type value: Decimal
        """
        self.__excise = Decimal(str(value))

    @property
    def supplier(self):
        """
        Возвращает supplier модели ReceiptItemResponse.

        :return: supplier модели ReceiptItemResponse.
        :rtype: ReceiptItemSupplier
        """
        return self.__supplier

    @supplier.setter
    def supplier(self, value):
        """
        Устанавливает supplier модели ReceiptItemResponse.

        :param value: supplier модели ReceiptItemResponse.
        :type value: ReceiptItemSupplier
        """
        if isinstance(value, dict):
            self.__supplier = ReceiptItemSupplier(value)
        else:
            self.__supplier = value

    @property
    def agent_type(self):
        """
        Возвращает agent_type модели ReceiptItemResponse.

        :return: agent_type модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__agent_type

    @agent_type.setter
    def agent_type(self, value):
        """
        Устанавливает agent_type модели ReceiptItemResponse.

        :param value: agent_type модели ReceiptItemResponse.
        :type value: str
        """
        self.__agent_type = str(value)

    @property
    def mark_code_info(self):
        """
        Возвращает mark_code_info модели ReceiptItemResponse.

        :return: mark_code_info модели ReceiptItemResponse.
        :rtype: MarkCodeInfo
        """
        return self.__mark_code_info

    @mark_code_info.setter
    def mark_code_info(self, value):
        """
        Устанавливает mark_code_info модели ReceiptItemResponse.

        :param value: mark_code_info модели ReceiptItemResponse.
        :type value: MarkCodeInfo
        """
        if isinstance(value, dict):
            self.__mark_code_info = MarkCodeInfo(value)
        else:
            self.__mark_code_info = value

    @property
    def measure(self):
        """
        Возвращает measure модели ReceiptItemResponse.

        :return: measure модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__measure

    @measure.setter
    def measure(self, value):
        """
        Устанавливает measure модели ReceiptItemResponse.

        :param value: measure модели ReceiptItemResponse.
        :type value: str
        """
        self.__measure = str(value)

    @property
    def payment_subject_industry_details(self):
        """
        Возвращает payment_subject_industry_details модели ReceiptItemResponse.

        :return: payment_subject_industry_details модели ReceiptItemResponse.
        :rtype: list[IndustryDetails]
        """
        return self.__payment_subject_industry_details

    @payment_subject_industry_details.setter
    def payment_subject_industry_details(self, value):
        """
        Устанавливает payment_subject_industry_details модели ReceiptItemResponse.

        :param value: payment_subject_industry_details модели ReceiptItemResponse.
        :type value: list[IndustryDetails]
        """
        if isinstance(value, list):
            self.__payment_subject_industry_details = [IndustryDetails(item) for item in value]
        else:
            self.__payment_subject_industry_details = []

    @property
    def product_code(self):
        """
        Возвращает product_code модели ReceiptItemResponse.

        :return: product_code модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__product_code

    @product_code.setter
    def product_code(self, value):
        """
        Устанавливает product_code модели ReceiptItemResponse.

        :param value: product_code модели ReceiptItemResponse.
        :type value: str
        """
        self.__product_code = str(value)

    @property
    def planned_status(self):
        """Возвращает planned_status модели ReceiptItemResponse.

        :return: planned_status модели ReceiptItemResponse.
        :rtype: int
        """
        return self.__planned_status

    @planned_status.setter
    def planned_status(self, value):
        """Устанавливает planned_status модели ReceiptItemResponse.

        :param value: planned_status модели ReceiptItemResponse.
        :type value: int
        """
        self.__planned_status = int(value)

    @property
    def mark_mode(self):
        """
        Возвращает mark_mode модели ReceiptItemResponse.

        :return: mark_mode модели ReceiptItemResponse.
        :rtype: str
        """
        return self.__mark_mode

    @mark_mode.setter
    def mark_mode(self, value):
        """
        Устанавливает mark_mode модели ReceiptItemResponse.

        :param value: mark_mode модели ReceiptItemResponse.
        :type value: str
        """
        self.__mark_mode = str(value)

    @property
    def mark_quantity(self):
        """
        Возвращает mark_quantity модели ReceiptItemResponse.

        :return: mark_quantity модели ReceiptItemResponse.
        :rtype: MarkQuantity
        """
        return self.__mark_quantity

    @mark_quantity.setter
    def mark_quantity(self, value):
        """
        Устанавливает mark_quantity модели ReceiptItemResponse.

        :param value: mark_quantity модели ReceiptItemResponse.
        :type value: MarkQuantity
        """
        if isinstance(value, dict):
            self.__mark_quantity = MarkQuantity(value)
        else:
            self.__mark_quantity = value

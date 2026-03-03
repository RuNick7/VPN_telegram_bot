# -*- coding: utf-8 -*-
import re
from decimal import Decimal

from yookassa.domain.common import BaseObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.mark_code_info import MarkCodeInfo
from yookassa.domain.models.receipt_data.mark_quantity import MarkQuantity


class ReceiptItem(BaseObject):
    """
    Информация о товарной позиции в заказе. Используется для формирования чека.
    """  # noqa: E501

    __description = None
    """Название товара (не более 128 символов). Тег в 54 ФЗ — 1030)."""  # noqa: E501

    __amount = None
    """Суммарная стоимость покупаемого товара в копейках/центах."""  # noqa: E501

    __vat_code = None
    """Ставка НДС, число 1-12 (тег в 54 ФЗ — 1199). Перечень возможных значений:  * %[для Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#vat-codes) * %[для сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#vat-codes) """  # noqa: E501

    __quantity = None
    """Количество товара (тег в 54 ФЗ — 1023). Формат: десятичное число, дробная часть — три знака или больше (количество знаков зависит от `quantity` в запросе). Разделитель дробной части — точка, разделитель тысяч отсутствует. Пример: ~`5.000` """  # noqa: E501

    __measure = None
    """Мера количества предмета расчета (тег в 54 ФЗ — 2108)."""  # noqa: E501

    __mark_quantity = None
    """Дробное количество маркированного товара (тег в 54 ФЗ — 1291)."""  # noqa: E501

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

    __product_code = None
    """Код товара — уникальный номер, который присваивается экземпляру товара при [маркировке](http://docs.cntd.ru/document/902192509) (тег в 54 ФЗ — 1162). <br/>Формат: число в шестнадцатеричном представлении с пробелами. Максимальная длина — 32 байта. Пример: ~`00 00 00 01 00 21 FA 41 00 23 05 41 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 12 00 AB 00`. <br/>Обязательный параметр, если товар нужно [маркировать](http://docs.cntd.ru/document/557297080). """  # noqa: E501

    __planned_status = None
    """Планируемый статус товара. Тег в 54 ФЗ — 2003. Указывается только для товаров, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`).  Перечень возможных значений:  * [для Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#planned-status) * [для сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#planned-status) """  # noqa: E501

    __mark_code_info = None
    """Код товара (тег в 54 ФЗ — 1163)."""  # noqa: E501

    __mark_mode = None
    """Режим обработки кода маркировки (тег в 54 ФЗ — 2102).  Обязательный параметр, если одновременно выполняются эти условия:  * вы используете Чеки от ЮKassa или онлайн-кассу Атол Онлайн или BusinessRu, обновленную до ФФД 1.2; * товар нужно [маркировать](http://docs.cntd.ru/document/902192509).  Должен принимать значение равное «0». """  # noqa: E501

    __payment_subject_industry_details = None
    """Отраслевой реквизит предмета расчета  (тег в 54 ФЗ — 1260). Обязателен при использовании ФФД 1.2."""  # noqa: E501

    @property
    def description(self):
        """
        Возвращает description модели ReceiptItem.

        :return: description модели ReceiptItem.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели ReceiptItem.

        :param value: description модели ReceiptItem.
        :type value: str
        """
        self.__description = str(value)

    @property
    def amount(self):
        """
        Возвращает amount модели ReceiptItem.

        :return: amount модели ReceiptItem.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели ReceiptItem.

        :param value: amount модели ReceiptItem.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def vat_code(self):
        """
        Возвращает vat_code модели ReceiptItem.

        :return: vat_code модели ReceiptItem.
        :rtype: int
        """
        return self.__vat_code

    @vat_code.setter
    def vat_code(self, value):
        """
        Устанавливает vat_code модели ReceiptItem.

        :param value: vat_code модели ReceiptItem.
        :type value: int
        """
        self.__vat_code = int(value)

    @property
    def quantity(self):
        """
        Возвращает quantity модели ReceiptItem.

        :return: quantity модели ReceiptItem.
        :rtype: Decimal
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """
        Устанавливает quantity модели ReceiptItem.

        :param value: quantity модели ReceiptItem.
        :type value: Decimal
        """
        self.__quantity = Decimal(str(float(value)))

    @property
    def measure(self):
        """
        Возвращает measure модели ReceiptItem.

        :return: measure модели ReceiptItem.
        :rtype: str
        """
        return self.__measure

    @measure.setter
    def measure(self, value):
        """
        Устанавливает measure модели ReceiptItem.

        :param value: measure модели ReceiptItem.
        :type value: str
        """
        self.__measure = value

    @property
    def mark_quantity(self):
        """
        Возвращает mark_quantity модели ReceiptItem.

        :return: mark_quantity модели ReceiptItem.
        :rtype: MarkQuantity
        """
        return self.__mark_quantity

    @mark_quantity.setter
    def mark_quantity(self, value):
        """
        Устанавливает mark_quantity модели ReceiptItem.

        :param value: mark_quantity модели ReceiptItem.
        :type value: MarkQuantity
        """
        if isinstance(value, dict):
            self.__mark_quantity = MarkQuantity(value)
        elif isinstance(value, MarkQuantity):
            self.__mark_quantity = value
        else:
            raise TypeError('Invalid mark_quantity data type in ReceiptItem.mark_quantity')

    @property
    def payment_subject(self):
        """
        Возвращает payment_subject модели ReceiptItem.

        :return: payment_subject модели ReceiptItem.
        :rtype: str
        """
        return self.__payment_subject

    @payment_subject.setter
    def payment_subject(self, value):
        """
        Устанавливает payment_subject модели ReceiptItem.

        :param value: payment_subject модели ReceiptItem.
        :type value: str
        """
        self.__payment_subject = str(value)

    @property
    def payment_mode(self):
        """
        Возвращает payment_mode модели ReceiptItem.

        :return: payment_mode модели ReceiptItem.
        :rtype: str
        """
        return self.__payment_mode

    @payment_mode.setter
    def payment_mode(self, value):
        """
        Устанавливает payment_mode модели ReceiptItem.

        :param value: payment_mode модели ReceiptItem.
        :type value: str
        """
        self.__payment_mode = str(value)

    @property
    def country_of_origin_code(self):
        """
        Возвращает country_of_origin_code модели ReceiptItem.

        :return: country_of_origin_code модели ReceiptItem.
        :rtype: str
        """
        return self.__country_of_origin_code

    @country_of_origin_code.setter
    def country_of_origin_code(self, value):
        """
        Устанавливает country_of_origin_code модели ReceiptItem.

        :param value: country_of_origin_code модели ReceiptItem.
        :type value: str
        """
        self.__country_of_origin_code = str(value)

    @property
    def customs_declaration_number(self):
        """
        Возвращает customs_declaration_number модели ReceiptItem.

        :return: customs_declaration_number модели ReceiptItem.
        :rtype: str
        """
        return self.__customs_declaration_number

    @customs_declaration_number.setter
    def customs_declaration_number(self, value):
        """
        Устанавливает customs_declaration_number модели ReceiptItem.

        :param value: customs_declaration_number модели ReceiptItem.
        :type value: str
        """
        self.__customs_declaration_number = str(value)

    @property
    def excise(self):
        """
        Возвращает excise модели ReceiptItem.

        :return: excise модели ReceiptItem.
        :rtype: str
        """
        return self.__excise

    @excise.setter
    def excise(self, value):
        """
        Устанавливает excise модели ReceiptItem.

        :param value: excise модели ReceiptItem.
        :type value: str
        """
        self.__excise = Decimal(str(value))

    @property
    def product_code(self):
        """
        Возвращает product_code модели ReceiptItem.

        :return: product_code модели ReceiptItem.
        :rtype: str
        """
        return self.__product_code

    @product_code.setter
    def product_code(self, value):
        """
        Устанавливает product_code модели ReceiptItem.

        :param value: product_code модели ReceiptItem.
        :type value: str
        """
        self.__product_code = str(value)

    @property
    def planned_status(self):
        """Возвращает planned_status модели ReceiptItem.

        :return: planned_status модели ReceiptItem.
        :rtype: int
        """
        return self.__planned_status

    @planned_status.setter
    def planned_status(self, value):
        """Устанавливает planned_status модели ReceiptItem.

        :param value: planned_status модели ReceiptItem.
        :type value: int
        """
        self.__planned_status = int(value)

    @property
    def mark_code_info(self):
        """
        Возвращает mark_code_info модели ReceiptItem.

        :return: mark_code_info модели ReceiptItem.
        :rtype: MarkCodeInfo
        """
        return self.__mark_code_info

    @mark_code_info.setter
    def mark_code_info(self, value):
        """
        Устанавливает mark_code_info модели ReceiptItem.

        :param value: mark_code_info модели ReceiptItem.
        :type value: MarkCodeInfo
        """
        if isinstance(value, dict):
            self.__mark_code_info = MarkCodeInfo(value)
        elif isinstance(value, MarkCodeInfo):
            self.__mark_code_info = value
        else:
            raise TypeError('Invalid mark_code_info data type in ReceiptItem.mark_code_info')

    @property
    def mark_mode(self):
        """
        Возвращает mark_mode модели ReceiptItem.

        :return: mark_mode модели ReceiptItem.
        :rtype: str
        """
        return self.__mark_mode

    @mark_mode.setter
    def mark_mode(self, value):
        """
        Устанавливает mark_mode модели ReceiptItem.

        :param value: mark_mode модели ReceiptItem.
        :type value: str
        """
        if value is not None and not re.search(r'^[0]{1}$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `mark_mode`, must be a follow pattern or equal to `/^[0]{1}$/`")  # noqa: E501
        self.__mark_mode = value

    @property
    def payment_subject_industry_details(self):
        """
        Возвращает payment_subject_industry_details модели ReceiptItem.

        :return: payment_subject_industry_details модели ReceiptItem.
        :rtype: list[IndustryDetails]
        """
        return self.__payment_subject_industry_details

    @payment_subject_industry_details.setter
    def payment_subject_industry_details(self, value):
        """
        Устанавливает payment_subject_industry_details модели ReceiptItem.

        :param value: payment_subject_industry_details модели ReceiptItem.
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
                    raise TypeError(
                        'Invalid payment_subject_industry_details data type in ReceiptItem.payment_subject_industry_details')
            self.__payment_subject_industry_details = items
        else:
            raise TypeError('Invalid payment_subject_industry_details value type in ReceiptItem')


class PaymentMode(object):
    """
    Признак способа расчета (тег в 54 ФЗ — 1214) — отражает тип оплаты и факт передачи товара. Пример: покупатель полностью оплачивает товар и сразу получает его. В этом случае нужно передать значение ~`full_payment` (полный расчет).
    Перечень возможных значений:
        * для Чеков от ЮKassa(/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#payment-mode)
        * для сторонних онлайн-касс(/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#payment-mode)
    """  # noqa: E501

    """
    Список допустимых значений
    """
    FULL_PREPAYMENT = 'full_prepayment'
    """Полная предоплата."""
    PARTIAL_PREPAYMENT = 'partial_prepayment'
    """Частичная предоплата."""
    ADVANCE = 'advance'
    """Аванс."""
    FULL_PAYMENT = 'full_payment'
    """Полный расчет."""
    PARTIAL_PAYMENT = 'partial_payment'
    """Частичный расчет и кредит."""
    CREDIT = 'credit'
    """Кредит."""
    CREDIT_PAYMENT = 'credit_payment'
    """Выплата по кредиту."""


class PaymentSubject(object):
    """
    Признак предмета расчета (тег в 54 ФЗ — 1212) — это то, за что принимается оплата, например товар, услуга.
    Перечень возможных значений:
        * для Чеков от ЮKassa(/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#payment-subject)
        * для сторонних онлайн-касс(/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#payment-subject)
    """  # noqa: E501

    """
    Список допустимых значений
    """
    COMMODITY = 'commodity'
    """Товар."""
    EXCISE = 'excise'
    """Подакцизный товар."""
    JOB = 'job'
    """Работа."""
    SERVICE = 'service'
    """Услуга."""
    GAMBLING_BET = 'gambling_bet'
    """Ставка в азартной игре."""
    GAMBLING_PRIZE = 'gambling_prize'
    """Выигрыш азартной игры."""
    LOTTERY = 'lottery'
    """Лотерейный билет."""
    LOTTERY_PRIZE = 'lottery_prize'
    """Выигрыш в лотерею."""
    INTELLECTUAL_ACTIVITY = 'intellectual_activity'
    """Результаты интеллектуальной деятельности."""
    PAYMENT = 'payment'
    """Платеж."""
    AGENT_COMMISSION = 'agent_commission'
    """Агентское вознаграждение."""
    COMPOSITE = 'composite'
    """Несколько вариантов."""
    ANOTHER = 'another'
    """Другое."""


class ReceiptItemMeasure(object):
    """
    Мера количества предмета расчета (тег в 54 ФЗ — 2108) — единица измерения товара, например штуки, граммы.
    Обязательный параметр, если используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2.
    Перечень возможных значений:
        * для Чеков от ЮKassa(/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#measure)
        * для сторонних онлайн-касс(/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#measure)
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PIECE = 'piece'
    """Штука, единица товара."""
    GRAM = 'gram'
    """Грамм."""
    KILOGRAM = 'kilogram'
    """Килограмм."""
    TON = 'ton'
    """Тонна."""
    CENTIMETER = 'centimeter'
    """Сантиметр."""
    DECIMETER = 'decimeter'
    """Дециметр."""
    METER = 'meter'
    """Метр."""
    SQUARE_CENTIMETER = 'square_centimeter'
    """Квадратный сантиметр."""
    SQUARE_DECIMETER = 'square_decimeter'
    """Квадратный дециметр."""
    SQUARE_METER = 'square_meter'
    """Квадратный метр."""
    MILLILITER = 'milliliter'
    """Миллилитр."""
    LITER = 'liter'
    """Литр."""
    CUBIC_METER = 'cubic_meter'
    """Кубический метр."""
    KILOWATT_HOUR = 'kilowatt_hour'
    """Килловат-час."""
    GIGACALORIE = 'gigacalorie'
    """Гигакалория."""
    DAY = 'day'
    """Сутки."""
    HOUR = 'hour'
    """Час."""
    MINUTE = 'minute'
    """Минута."""
    SECOND = 'second'
    """Секунда."""
    KILOBYTE = 'kilobyte'
    """Килобайт."""
    MEGABYTE = 'megabyte'
    """Мегабайт."""
    GIGABYTE = 'gigabyte'
    """Гигабайт."""
    TERABYTE = 'terabyte'
    """Терабайт."""
    ANOTHER = 'another'
    """Другое."""

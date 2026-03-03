# -*- coding: utf-8 -*-
from yookassa.domain.common import ResponseObject
from yookassa.domain.models import Settlement
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.operational_details import OperationalDetails
from yookassa.domain.response import ReceiptItemResponse


class ReceiptResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о чеке.
    """  # noqa: E501

    __id = None
    """Идентификатор чека в ЮKassa."""  # noqa: E501

    __type = None
    """Тип чека в онлайн-кассе: приход (payment) или возврат прихода (refund)."""  # noqa: E501

    __refund_id = None
    """Идентификатор возврата, для которого был сформирован чек. Отсутствует в чеке платежа."""  # noqa: E501

    __payment_id = None
    """Идентификатор платежа, для которого был сформирован чек."""  # noqa: E501

    __status = None
    """Статус доставки данных для чека в онлайн-кассу. """  # noqa: E501

    __fiscal_document_number = None
    """Номер фискального документа."""  # noqa: E501

    __fiscal_storage_number = None
    """Номер фискального накопителя в кассовом аппарате."""  # noqa: E501

    __fiscal_attribute = None
    """Фискальный признак чека. Формируется фискальным накопителем на основе данных, переданных для регистрации чека."""  # noqa: E501

    __registered_at = None
    """Дата и время формирования чека в фискальном накопителе. Указывается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601)."""  # noqa: E501

    __fiscal_provider_id = None
    """Идентификатор чека в онлайн-кассе. Присутствует, если чек удалось зарегистрировать."""  # noqa: E501

    __items = []
    """Список товаров в чеке: для [Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/basics) — не более 80 товаров, для [сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/basics) — не более 100 товаров. """  # noqa: E501

    __internet = None
    """Признак проведения платежа в интернете (тег в 54 ФЗ — 1125) — указывает на оплату через интернет.  Возможные значения: * ~`true` — оплата прошла онлайн, через интернет (например, на вашем сайте или в приложении); * ~`false` — оплата прошла офлайн, при личном взаимодействии (например, в торговой точке или при встрече с курьером). По умолчанию ~`true`. Если вы принимаете платежи офлайн, передайте в запросе значение ~`false`. """  # noqa: E501

    __settlements = []
    """Перечень совершенных расчетов."""  # noqa: E501

    __on_behalf_of = None
    """Идентификатор магазина, от имени которого нужно отправить чек. Выдается ЮKassa."""  # noqa: E501

    __timezone = None
    """Номер часовой зоны для адреса, по которому вы принимаете платежи (тег в 54 ФЗ — 1011).  Указывается, только если в чеке есть товары, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`). """  # noqa: E501

    __tax_system_code = None
    """Система налогообложения магазина (тег в 54 ФЗ — 1055)."""  # noqa: E501

    __receipt_industry_details = []
    """Отраслевой реквизит предмета расчета (тег в 54 ФЗ — 1260)."""  # noqa: E501

    __receipt_operational_details = None
    """Операционный реквизит чека (тег в 54 ФЗ — 1270)."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели ReceiptResponse.

        :return: id модели ReceiptResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели ReceiptResponse.

        :param value: id модели ReceiptResponse.
        :type value: str
        """
        self.__id = str(value)

    @property
    def type(self):
        """
        Возвращает type модели ReceiptResponse.

        :return: type модели ReceiptResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели ReceiptResponse.

        :param value: type модели ReceiptResponse.
        :type value: str
        """
        self.__type = str(value)

    @property
    def payment_id(self):
        """
        Возвращает payment_id модели ReceiptResponse.

        :return: payment_id модели ReceiptResponse.
        :rtype: str
        """
        return self.__payment_id

    @payment_id.setter
    def payment_id(self, value):
        """
        Устанавливает payment_id модели ReceiptResponse.

        :param value: payment_id модели ReceiptResponse.
        :type value: str
        """
        self.__payment_id = str(value)

    @property
    def refund_id(self):
        """
        Возвращает refund_id модели ReceiptResponse.

        :return: refund_id модели ReceiptResponse.
        :rtype: str
        """
        return self.__refund_id

    @refund_id.setter
    def refund_id(self, value):
        """
        Устанавливает refund_id модели ReceiptResponse.

        :param value: refund_id модели ReceiptResponse.
        :type value: str
        """
        self.__refund_id = str(value)

    @property
    def status(self):
        """
        Возвращает status модели ReceiptResponse.

        :return: status модели ReceiptResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели ReceiptResponse.

        :param value: status модели ReceiptResponse.
        :type value: str
        """
        self.__status = str(value)

    @property
    def receipt_registration(self):
        """
        Возвращает status модели ReceiptResponse.

        :return: status модели ReceiptResponse.
        :rtype: str
        """
        return self.status

    @receipt_registration.setter
    def receipt_registration(self, value):
        """
        Устанавливает status модели ReceiptResponse.

        :param value: status модели ReceiptResponse.
        :type value: str
        """
        self.status = value

    @property
    def fiscal_document_number(self):
        """
        Возвращает fiscal_document_number модели ReceiptResponse.

        :return: fiscal_document_number модели ReceiptResponse.
        :rtype: str
        """
        return self.__fiscal_document_number

    @fiscal_document_number.setter
    def fiscal_document_number(self, value):
        """
        Устанавливает fiscal_document_number модели ReceiptResponse.

        :param value: fiscal_document_number модели ReceiptResponse.
        :type value: str
        """
        self.__fiscal_document_number = str(value)

    @property
    def fiscal_storage_number(self):
        """
        Возвращает fiscal_storage_number модели ReceiptResponse.

        :return: fiscal_storage_number модели ReceiptResponse.
        :rtype: str
        """
        return self.__fiscal_storage_number

    @fiscal_storage_number.setter
    def fiscal_storage_number(self, value):
        """
        Устанавливает fiscal_storage_number модели ReceiptResponse.

        :param value: fiscal_storage_number модели ReceiptResponse.
        :type value: str
        """
        self.__fiscal_storage_number = str(value)

    @property
    def fiscal_attribute(self):
        """
        Возвращает fiscal_attribute модели ReceiptResponse.

        :return: fiscal_attribute модели ReceiptResponse.
        :rtype: str
        """
        return self.__fiscal_attribute

    @fiscal_attribute.setter
    def fiscal_attribute(self, value):
        """
        Устанавливает fiscal_attribute модели ReceiptResponse.

        :param value: fiscal_attribute модели ReceiptResponse.
        :type value: str
        """
        self.__fiscal_attribute = str(value)

    @property
    def registered_at(self):
        """
        Возвращает registered_at модели ReceiptResponse.

        :return: registered_at модели ReceiptResponse.
        :rtype: datetime
        """
        return self.__registered_at

    @registered_at.setter
    def registered_at(self, value):
        """
        Устанавливает registered_at модели ReceiptResponse.

        :param value: registered_at модели ReceiptResponse.
        :type value: datetime
        """
        self.__registered_at = value

    @property
    def fiscal_provider_id(self):
        """
        Возвращает fiscal_provider_id модели ReceiptResponse.

        :return: fiscal_provider_id модели ReceiptResponse.
        :rtype: str
        """
        return self.__fiscal_provider_id

    @fiscal_provider_id.setter
    def fiscal_provider_id(self, value):
        """
        Устанавливает fiscal_provider_id модели ReceiptResponse.

        :param value: fiscal_provider_id модели ReceiptResponse.
        :type value: str
        """
        self.__fiscal_provider_id = str(value)

    @property
    def items(self):
        """
        Возвращает items модели ReceiptResponse.

        :return: items модели ReceiptResponse.
        :rtype: list[ReceiptItemResponse]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели ReceiptResponse.

        :param value: items модели ReceiptResponse.
        :type value: list[ReceiptItemResponse]
        """
        if isinstance(value, list):
            self.__items = [ReceiptItemResponse(item) for item in value]
        else:
            self.__items = []

    @property
    def internet(self):
        """
        Возвращает internet модели ReceiptResponse.

        :return: internet модели ReceiptResponse.
        :rtype: bool
        """
        return self.__internet

    @internet.setter
    def internet(self, value):
        """
        Устанавливает internet модели ReceiptResponse.

        :param value: internet модели ReceiptResponse.
        :type value: bool
        """
        self.__internet = bool(value)

    @property
    def settlements(self):
        """
        Возвращает settlements модели ReceiptResponse.

        :return: settlements модели ReceiptResponse.
        :rtype: list[Settlement]
        """
        return self.__settlements

    @settlements.setter
    def settlements(self, value):
        """
        Устанавливает settlements модели ReceiptResponse.

        :param value: settlements модели ReceiptResponse.
        :type value: list[Settlement]
        """
        if isinstance(value, list):
            self.__settlements = [Settlement(item) for item in value]
        else:
            self.__settlements = []

    @property
    def on_behalf_of(self):
        """
        Возвращает on_behalf_of модели ReceiptResponse.

        :return: on_behalf_of модели ReceiptResponse.
        :rtype: str
        """
        return self.__on_behalf_of

    @on_behalf_of.setter
    def on_behalf_of(self, value):
        """
        Устанавливает on_behalf_of модели ReceiptResponse.

        :param value: on_behalf_of модели ReceiptResponse.
        :type value: str
        """
        self.__on_behalf_of = str(value)

    @property
    def tax_system_code(self):
        """
        Возвращает tax_system_code модели ReceiptResponse.

        :return: tax_system_code модели ReceiptResponse.
        :rtype: int
        """
        return self.__tax_system_code

    @tax_system_code.setter
    def tax_system_code(self, value):
        """
        Устанавливает tax_system_code модели ReceiptResponse.

        :param value: tax_system_code модели ReceiptResponse.
        :type value: int
        """
        self.__tax_system_code = int(value)

    @property
    def timezone(self):
        """
        Возвращает timezone модели ReceiptResponse.

        :return: timezone модели ReceiptResponse.
        :rtype: int
        """
        return self.__timezone

    @timezone.setter
    def timezone(self, value):
        """
        Устанавливает timezone модели ReceiptResponse.

        :param value: timezone модели ReceiptResponse.
        :type value: int
        """
        self.__timezone = int(value)

    @property
    def receipt_industry_details(self):
        """
        Возвращает receipt_industry_details модели ReceiptResponse.

        :return: receipt_industry_details модели ReceiptResponse.
        :rtype: list[IndustryDetails]
        """
        return self.__receipt_industry_details

    @receipt_industry_details.setter
    def receipt_industry_details(self, value):
        """
        Устанавливает receipt_industry_details модели ReceiptResponse.

        :param value: receipt_industry_details модели ReceiptResponse.
        :type value: list[IndustryDetails]
        """
        if isinstance(value, list):
            self.__receipt_industry_details = [IndustryDetails(item) for item in value]
        else:
            self.__receipt_industry_details = []

    @property
    def receipt_operational_details(self):
        """
        Возвращает receipt_operational_details модели ReceiptResponse.

        :return: receipt_operational_details модели ReceiptResponse.
        :rtype: OperationalDetails
        """
        return self.__receipt_operational_details

    @receipt_operational_details.setter
    def receipt_operational_details(self, value):
        """
        Устанавливает receipt_operational_details модели ReceiptResponse.

        :param value: receipt_operational_details модели ReceiptResponse.
        :type value: OperationalDetails
        """
        if isinstance(value, dict):
            self.__receipt_operational_details = OperationalDetails(value)
        else:
            self.__receipt_operational_details = value

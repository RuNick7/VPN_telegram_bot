# -*- coding: utf-8 -*-
from yookassa.domain.common.receipt_type import ReceiptType
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.receipt_data.receipt_customer import ReceiptCustomer
from yookassa.domain.models.receipt_data.additional_user_props import AdditionalUserProps
from yookassa.domain.models.receipt_data.industry_details import IndustryDetails
from yookassa.domain.models.receipt_data.operational_details import OperationalDetails
from yookassa.domain.models.settlement import Settlement
from yookassa.domain.request.receipt_item_request import ReceiptItemRequest


class ReceiptRequest(RequestObject):
    """
    Объект запроса к API на создание чека.
    """  # noqa: E501

    __type = None
    """Тип чека в онлайн-кассе: приход "payment" или возврат "refund"."""  # noqa: E501

    __payment_id = None
    """Идентификатор платежа в ЮKassa для отображения информации о чеке в личном кабинете, на платеж не влияет. Обязательный параметр при создании чека прихода. """  # noqa: E501

    __refund_id = None
    """Идентификатор возврата в ЮKassa для отображения информации о чеке в личном кабинете. Обязательный параметр при создании чека возврата прихода."""  # noqa: E501

    __customer = None
    """Информация о пользователе."""  # noqa: E501

    __items = []
    """Список товаров в чеке: для [Чеков от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/basics) — не более 80 товаров, для [сторонних онлайн-касс](/developers/payment-acceptance/receipts/54fz/other-services/basics) — не более 100 товаров. """  # noqa: E501

    __internet = None
    """Признак проведения платежа в интернете (тег в 54 ФЗ — 1125) — указывает на оплату через интернет.  Возможные значения: * ~`true` — оплата прошла онлайн, через интернет (например, на вашем сайте или в приложении); * ~`false` — оплата прошла офлайн, при личном взаимодействии (например, в торговой точке или при встрече с курьером). По умолчанию ~`true`. Если вы принимаете платежи офлайн, передайте в запросе значение ~`false`. """  # noqa: E501

    __send = None
    """Формирование чека в онлайн-кассе сразу после создания объекта чека. Сейчас можно передать только значение ~`true`. """  # noqa: E501

    __tax_system_code = None
    """Система налогообложения магазина (тег в 54 ФЗ — 1055).  Для сторонних онлайн-касс: обязательный параметр, если вы используете онлайн-кассу Атол Онлайн, обновленную до ФФД 1.2, или у вас несколько систем налогообложения, в остальных случаях не передается. %[Перечень возможных значений](/developers/payment-acceptance/receipts/54fz/other-services/parameters-values#tax-systems)  Для Чеков от ЮKassa: параметр передавать не нужно, ЮKassa его проигнорирует. """  # noqa: E501

    __additional_user_props = None
    """Дополнительный реквизит пользователя."""  # noqa: E501

    __timezone = None
    """Номер часовой зоны для адреса, по которому вы принимаете платежи (тег в 54 ФЗ — 1011).  Указывается, только если в чеке есть товары, которые подлежат обязательной маркировке (в `items.mark_code_info` передается параметр `gs_1m`, `short` или `fur`). """  # noqa: E501

    __receipt_industry_details = None
    """Отраслевой реквизит чека (тег в 54 ФЗ — 1261). Нужно передавать, если используете ФФД 1.2."""  # noqa: E501

    __receipt_operational_details = None
    """Операционный реквизит чека."""  # noqa: E501

    __settlements = []
    """Перечень совершенных расчетов."""  # noqa: E501

    __on_behalf_of = None
    """Идентификатор магазина в ЮKassa."""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели ReceiptRequest.

        :return: type модели ReceiptRequest.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели ReceiptRequest.

        :param value: type модели ReceiptRequest.
        :type value: str
        """
        self.__type = str(value)

    @property
    def payment_id(self):
        """
        Возвращает payment_id модели ReceiptRequest.

        :return: payment_id модели ReceiptRequest.
        :rtype: str
        """
        return self.__payment_id

    @payment_id.setter
    def payment_id(self, value):
        """
        Устанавливает payment_id модели ReceiptRequest.

        :param value: payment_id модели ReceiptRequest.
        :type value: str
        """
        self.__refund_id = None
        self.__payment_id = str(value)

    @property
    def refund_id(self):
        """
        Возвращает refund_id модели ReceiptRequest.

        :return: refund_id модели ReceiptRequest.
        :rtype: str
        """
        return self.__refund_id

    @refund_id.setter
    def refund_id(self, value):
        """
        Устанавливает refund_id модели ReceiptRequest.

        :param value: refund_id модели ReceiptRequest.
        :type value: str
        """
        self.__payment_id = None
        self.__refund_id = str(value)

    @property
    def customer(self):
        """
        Возвращает customer модели ReceiptRequest.

        :return: customer модели ReceiptRequest.
        :rtype: ReceiptCustomer
        """
        return self.__customer

    @customer.setter
    def customer(self, value):
        """
        Устанавливает customer модели ReceiptRequest.

        :param value: customer модели ReceiptRequest.
        :type value: ReceiptCustomer
        """
        if isinstance(value, dict):
            self.__customer = ReceiptCustomer(value)
        elif isinstance(value, ReceiptCustomer):
            self.__customer = value
        else:
            raise TypeError('Invalid customer value type in ReceiptRequest')

    @property
    def email(self):
        """
        Возвращает email модели ReceiptRequest.

        :return: email модели ReceiptRequest.
        :rtype: str
        """
        return self.__customer.email if self.__customer is not None else None

    @email.setter
    def email(self, value):
        """
        Устанавливает email модели ReceiptRequest.

        :param value: email модели ReceiptRequest.
        :type value: str
        """
        if self.__customer is None:
            self.__customer = ReceiptCustomer()
        self.__customer.email = str(value)

    @property
    def phone(self):
        """
        Возвращает phone модели ReceiptRequest.

        :return: phone модели ReceiptRequest.
        :rtype: str
        """
        return self.__customer.phone if self.__customer is not None else None

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели ReceiptRequest.

        :param value: phone модели ReceiptRequest.
        :type value: str
        """
        if self.__customer is None:
            self.__customer = ReceiptCustomer()
        self.__customer.phone = str(value)

    @property
    def items(self):
        """
        Возвращает items модели ReceiptRequest.

        :return: items модели ReceiptRequest.
        :rtype: list[ReceiptItemRequest]
        """
        return self.__items

    @items.setter
    def items(self, value):
        """
        Устанавливает items модели ReceiptRequest.

        :param value: items модели ReceiptRequest.
        :type value: list[ReceiptItemRequest]
        """
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append(ReceiptItemRequest(item))
                elif isinstance(item, ReceiptItemRequest):
                    items.append(item)
                else:
                    raise TypeError('Invalid item type in ReceiptRequest.items')
            self.__items = items
        elif value is None:
            self.__items = []
        else:
            raise TypeError('Invalid items value type in ReceiptRequest')

    @property
    def internet(self):
        """
        Возвращает internet модели ReceiptRequest.

        :return: internet модели ReceiptRequest.
        :rtype: bool
        """
        return self.__internet

    @internet.setter
    def internet(self, value):
        """
        Устанавливает internet модели ReceiptRequest.

        :param value: internet модели ReceiptRequest.
        :type value: bool
        """
        if isinstance(value, bool):
            self.__internet = value
        else:
            raise TypeError('Invalid internet value type in ReceiptRequest')

    @property
    def send(self):
        """
        Возвращает send модели ReceiptRequest.

        :return: send модели ReceiptRequest.
        :rtype: bool
        """
        return self.__send

    @send.setter
    def send(self, value):
        """
        Устанавливает send модели ReceiptRequest.

        :param value: send модели ReceiptRequest.
        :type value: bool
        """
        if isinstance(value, bool):
            self.__send = value
        else:
            raise TypeError('Invalid send value type in ReceiptRequest')

    @property
    def tax_system_code(self):
        """
        Возвращает tax_system_code модели ReceiptRequest.

        :return: tax_system_code модели ReceiptRequest.
        :rtype: int
        """
        return self.__tax_system_code

    @tax_system_code.setter
    def tax_system_code(self, value):
        """
        Устанавливает tax_system_code модели ReceiptRequest.

        :param value: tax_system_code модели ReceiptRequest.
        :type value: int
        """
        if isinstance(value, int):
            self.__tax_system_code = value
        else:
            raise TypeError('Invalid tax_system_code value type in ReceiptRequest')

    @property
    def timezone(self):
        """
        Возвращает timezone модели ReceiptRequest.

        :return: timezone модели ReceiptRequest.
        :rtype: int
        """
        return self.__timezone

    @timezone.setter
    def timezone(self, value):
        """
        Устанавливает timezone модели ReceiptRequest.

        :param value: timezone модели ReceiptRequest.
        :type value: int
        """
        if value is not None and value > 11:  # noqa: E501
            raise ValueError("Invalid value for `timezone`, must be a value less than or equal to `11`")  # noqa: E501
        if value is not None and value < 1:  # noqa: E501
            raise ValueError("Invalid value for `timezone`, must be a value greater than or equal to `1`")  # noqa: E501
        self.__timezone = value

    @property
    def additional_user_props(self):
        """
        Возвращает additional_user_props модели ReceiptRequest.

        :return: additional_user_props модели ReceiptRequest.
        :rtype: AdditionalUserProps
        """
        return self.__additional_user_props

    @additional_user_props.setter
    def additional_user_props(self, value):
        """
        Устанавливает additional_user_props модели ReceiptRequest.

        :param value: additional_user_props модели ReceiptRequest.
        :type value: AdditionalUserProps
        """
        if isinstance(value, dict):
            self.__additional_user_props = AdditionalUserProps(value)
        elif isinstance(value, AdditionalUserProps):
            self.__additional_user_props = value
        else:
            raise TypeError('Invalid additional_user_props data type in ReceiptRequest')

    @property
    def receipt_industry_details(self):
        """
        Возвращает receipt_industry_details модели ReceiptRequest.

        :return: receipt_industry_details модели ReceiptRequest.
        :rtype: list[IndustryDetails]
        """
        return self.__receipt_industry_details

    @receipt_industry_details.setter
    def receipt_industry_details(self, value):
        """
        Устанавливает receipt_industry_details модели ReceiptRequest.

        :param value: receipt_industry_details модели ReceiptRequest.
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
                    raise TypeError('Invalid receipt_industry_details data type in ReceiptRequest.receipt_industry_details')
            self.__receipt_industry_details = items
        else:
            raise TypeError('Invalid receipt_industry_details value type in ReceiptRequest')

    @property
    def receipt_operational_details(self):
        """
        Возвращает receipt_operational_details модели ReceiptRequest.

        :return: receipt_operational_details модели ReceiptRequest.
        :rtype: OperationalDetails
        """
        return self.__receipt_operational_details

    @receipt_operational_details.setter
    def receipt_operational_details(self, value):
        """
        Устанавливает receipt_operational_details модели ReceiptRequest.

        :param value: receipt_operational_details модели ReceiptRequest.
        :type value: OperationalDetails
        """
        if isinstance(value, dict):
            self.__receipt_operational_details = OperationalDetails(value)
        elif isinstance(value, OperationalDetails):
            self.__receipt_operational_details = value
        else:
            raise TypeError('Invalid receipt_operational_details data type in ReceiptRequest')

    @property
    def settlements(self):
        """
        Возвращает settlements модели ReceiptRequest.

        :return: settlements модели ReceiptRequest.
        :rtype: list[Settlement]
        """
        return self.__settlements

    @settlements.setter
    def settlements(self, value):
        """
        Устанавливает settlements модели ReceiptRequest.

        :param value: settlements модели ReceiptRequest.
        :type value: list[Settlement]
        """
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append(Settlement(item))
                elif isinstance(item, Settlement):
                    items.append(item)
                else:
                    raise TypeError('Invalid settlement type in ReceiptRequest.settlements')
            self.__settlements = items
        elif value is None:
            self.__settlements = []
        else:
            raise TypeError('Invalid settlements value type in ReceiptRequest')

    @property
    def on_behalf_of(self):
        """
        Возвращает on_behalf_of модели ReceiptRequest.

        :return: on_behalf_of модели ReceiptRequest.
        :rtype: str
        """
        return self.__on_behalf_of

    @on_behalf_of.setter
    def on_behalf_of(self, value):
        """
        Устанавливает on_behalf_of модели ReceiptRequest.

        :param value: on_behalf_of модели ReceiptRequest.
        :type value: str
        """
        self.__on_behalf_of = str(value)

    def validate(self):
        """
        Влидация данных модели ReceiptRequest.
        """
        if self.type is None:
            self.__set_validation_error('ReceiptRequest.type not specified')

        if self.send is None:
            self.__set_validation_error('ReceiptRequest.send not specified')

        if self.customer is None:
            self.__set_validation_error('ReceiptRequest.customer not specified')

        email = self.customer.email
        phone = self.customer.phone
        if not email and not phone:
            self.__set_validation_error('Both email and phone values are empty in ReceiptRequest.customer')

        if not self.has_items():
            self.__set_validation_error('ReceiptRequest.items not specified')

        if not self.has_settlements():
            self.__set_validation_error('ReceiptRequest.settlements not specified')

        if self.type is ReceiptType.PAYMENT and self.payment_id is None:
            self.__set_validation_error('ReceiptRequest.payment_id not specified')

        if self.type is ReceiptType.REFUND and self.refund_id is None and self.payment_id is None:
            self.__set_validation_error('ReceiptRequest.refund_id or ReceiptRequest.payment_id not specified')

    def has_items(self):
        """
        Проверяет, были ли установлены товары в чеке модели ReceiptRequest.

        :rtype: bool
        """
        return bool(self.items) and bool(len(self.items))

    def has_settlements(self):
        """
        Проверяет, был ли установлен перечень расчетов модели ReceiptRequest.

        :rtype: bool
        """
        return bool(self.settlements) and bool(len(self.settlements))

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели ReceiptRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

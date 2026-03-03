# coding: utf-8

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Amount


class InvoiceStatus:
    """
    Статус счета.
    Возможные значения:
    - `pending` — счет создан и ожидает успешной оплаты;
    - `succeeded` — счет успешно оплачен, есть связанный платеж в статусе ~`succeeded` (финальный и неизменяемый статус для платежей в одну стадию);
    - `canceled` — вы отменили счет, успешный платеж по нему не поступил или был отменен (при оплате в две стадии) либо истек срок действия счета (финальный и неизменяемый статус).

    Подробнее про [жизненный цикл счета](/developers/payment-acceptance/scenario-extensions/invoices/basics#invoice-status)
    """  # noqa: E501

    """
    Список допустимых значений
    """
    PENDING = "pending"
    """Счет создан и ожидает успешной оплаты"""
    SUCCEEDED = "succeeded"
    """Счет успешно оплачен, есть связанный платеж в статусе ~`succeeded`"""
    CANCELED = "canceled"
    """Вы отменили счет, успешный платеж по нему не поступил или был отменен"""


class DeliveryMethodType:
    """
    Класс, представляющий модель DeliveryMethodType.

    Код способа доставки счета пользователю.
    Возможные значения:
    - `self` — Самостоятельно;
    - `email` — По электронной почте;
    - `sms` — В смс;
    Подробнее про [жизненный цикл счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics)
    """  # noqa: E501

    """
    Список допустимых значений
    """
    SELF = "self"
    """Самостоятельно"""
    EMAIL = "email"
    """По электронной почте"""
    SMS = "sms"
    """В смс"""
    UNKNOWN = "unknown"
    """Для неизвестных методов доставки счета пользователю"""


class LineItem(BaseObject):
    """Данные о товаре или услуге в корзине."""  # noqa: E501

    __description = None
    """Название товара или услуги (от 1 до 128 символов). Пользователь увидит его на странице счета перед оплатой."""  # noqa: E501

    __price = None
    """Полная цена товара или услуги. Пользователь увидит ее на странице счета перед оплатой."""  # noqa: E501

    __discount_price = None
    """Итоговая цена товара с учетом скидки. Если передана, то на странице счета цена отобразится с учетом скидки. Не нужно передавать, если пользователь оплачивает полную стоимость товара или услуги."""  # noqa: E501

    __quantity = None
    """Количество товара. Можно передать целое или дробное число. Разделитель дробной части — точка, разделитель тысяч отсутствует, максимум три знака после точки. Пример: ~`5.000` """  # noqa: E501

    @property
    def description(self):
        """Возвращает description модели LineItem.

        :return: description модели LineItem.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """Устанавливает description модели LineItem.

        :param value: description модели LineItem.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `description`, must not be `None`")  # noqa: E501
        self.__description = value

    @property
    def price(self):
        """Возвращает price модели LineItem.

        :return: price модели LineItem.
        :rtype: LineItemPrice
        """
        return self.__price

    @price.setter
    def price(self, value):
        """Устанавливает price модели LineItem.

        :param value: price модели LineItem.
        :type value: LineItemPrice
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `price`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__price = Amount(value)
        elif isinstance(value, Amount):
            self.__price = value
        else:
            raise TypeError('Invalid price data type in LineItem.price')

    @property
    def discount_price(self):
        """Возвращает discount_price модели LineItem.

        :return: discount_price модели LineItem.
        :rtype: LineItemDiscountPrice
        """
        return self.__discount_price

    @discount_price.setter
    def discount_price(self, value):
        """Устанавливает discount_price модели LineItem.

        :param value: discount_price модели LineItem.
        :type value: LineItemDiscountPrice
        """
        if isinstance(value, dict):
            self.__discount_price = Amount(value)
        elif isinstance(value, Amount):
            self.__discount_price = value
        else:
            raise TypeError('Invalid discount_price data type in LineItem.discount_price')

    @property
    def quantity(self):
        """Возвращает quantity модели LineItem.

        :return: quantity модели LineItem.
        :rtype: float
        """
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        """Устанавливает quantity модели LineItem.

        :param value: quantity модели LineItem.
        :type value: float
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `quantity`, must not be `None`")  # noqa: E501
        self.__quantity = value


class PaymentDetails(BaseObject):
    """Данные о платеже по выставленному счету. Присутствуют, только если платеж успешно %[подтвержден пользователем](/developers/payment-acceptance/getting-started/payment-process#user-confirmation). """  # noqa: E501

    __id = None
    """Идентификатор платежа в ЮKassa."""  # noqa: E501

    __status = None
    """Статус платежа."""  # noqa: E501

    @property
    def id(self):
        """Возвращает id модели PaymentDetails.

        :return: id модели PaymentDetails.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """Устанавливает id модели PaymentDetails.

        :param value: id модели PaymentDetails.
        :type value: str
        """
        self.__id = value

    @property
    def status(self):
        """Возвращает status модели PaymentDetails.

        :return: status модели PaymentDetails.
        :rtype: PaymentStatus
        """
        return self.__status

    @status.setter
    def status(self, value):
        """Устанавливает status модели PaymentDetails.

        :param value: status модели PaymentDetails.
        :type value: PaymentStatus
        """
        self.__status = value

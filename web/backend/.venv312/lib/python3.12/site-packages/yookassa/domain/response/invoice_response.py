# coding: utf-8

from yookassa.domain.common import ResponseObject
from yookassa.domain.models import CancellationDetails
from yookassa.domain.models.invoice import PaymentDetails, LineItem, DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method_class_map import DeliveryMethodClassMap
from yookassa.domain.models.invoice_data.delivery_method_factory import DeliveryMethodFactory


class InvoiceResponse(ResponseObject):
    """Объект счета (Invoice) — актуальная информация о счете."""  # noqa: E501

    __id = None
    """Идентификатор счета в ЮКасса."""  # noqa: E501

    __status = None
    """Статус счета. Возможные значения: `pending`, `succeeded`, `canceled`."""  # noqa: E501

    __cart = None
    """Корзина заказа — список товаров или услуг, который отобразится на странице счета перед оплатой."""  # noqa: E501

    __delivery_method = None
    """Данные о выбранном способе доставки счета. Присутствует только для счетов в статусе `pending`."""  # noqa: E501

    __payment_details = None
    """Данные о платеже по выставленному счету. Присутствуют, только если платеж успешно [подтвержден пользователем](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation)."""  # noqa: E501

    __created_at = None
    """Дата и время создания счета на оплату. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __expires_at = None
    """
    Срок действия счета — дата и время, до которых можно оплатить выставленный счет. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601).
    Пример: `2024-10-18T10:51:18.139Z`
    Присутствует только для счетов в статусе `pending`.
    """  # noqa: E501

    __description = None
    """Описание выставленного счета (не более 128 символов), которое вы увидите в личном кабинете ЮKassa, а пользователь на странице счета. Например: «Счет на оплату по договору 37». """  # noqa: E501

    __cancellation_details = None
    """Комментарий к статусу canceled: кто отменил счет и по какой причине."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def id(self):
        """Возвращает id модели InvoiceResponse.

        :return: id модели InvoiceResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """Устанавливает id модели InvoiceResponse.

        :param value: id модели InvoiceResponse.
        :type value: str
        """
        self.__id = value

    @property
    def status(self):
        """Возвращает status модели InvoiceResponse.

        :return: status модели InvoiceResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """Устанавливает status модели InvoiceResponse.

        :param value: status модели InvoiceResponse.
        :type value: str
        """
        self.__status = value

    @property
    def cart(self):
        """Возвращает cart модели InvoiceResponse.

        :return: cart модели InvoiceResponse.
        :rtype: list[LineItem]
        """
        return self.__cart

    @cart.setter
    def cart(self, value):
        """Устанавливает cart модели InvoiceResponse.

        :param value: cart модели InvoiceResponse.
        :type value: list[LineItem]
        """
        if isinstance(value, list):
            cart_array = []
            for cartData in value:
                if isinstance(cartData, dict):
                    cart_array.append(LineItem(cartData))
                elif isinstance(cartData, LineItem):
                    cart_array.append(cartData)
                else:
                    raise TypeError('Invalid cart data type in InvoiceResponse.cart')

            self.__cart = cart_array

    @property
    def delivery_method(self):
        """Возвращает delivery_method модели InvoiceResponse.

        :return: delivery_method модели InvoiceResponse.
        :rtype: InvoiceDeliveryMethod
        """
        return self.__delivery_method

    @delivery_method.setter
    def delivery_method(self, value):
        """Устанавливает delivery_method модели InvoiceResponse.

        :param value: delivery_method модели InvoiceResponse.
        :type value: InvoiceDeliveryMethod
        """
        if isinstance(value, dict) and 'type' in value and value['type'] not in DeliveryMethodClassMap().response:
            value['type'] = DeliveryMethodType.UNKNOWN
        self.__delivery_method = DeliveryMethodFactory().create(value, self.context())

    @property
    def payment_details(self):
        """Возвращает payment_details модели InvoiceResponse.

        :return: payment_details модели InvoiceResponse.
        :rtype: PaymentDetails
        """
        return self.__payment_details

    @payment_details.setter
    def payment_details(self, value):
        """Устанавливает payment_details модели InvoiceResponse.

        :param value: payment_details модели InvoiceResponse.
        :type value: PaymentDetails
        """
        self.__payment_details = PaymentDetails(value)

    @property
    def created_at(self):
        """Возвращает created_at модели InvoiceResponse.

        :return: created_at модели InvoiceResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """Устанавливает created_at модели InvoiceResponse.

        :param value: created_at модели InvoiceResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def expires_at(self):
        """Возвращает expires_at модели InvoiceResponse.

        :return: expires_at модели InvoiceResponse.
        :rtype: datetime
        """
        return self.__expires_at

    @expires_at.setter
    def expires_at(self, value):
        """Устанавливает expires_at модели InvoiceResponse.

        :param value: expires_at модели InvoiceResponse.
        :type value: datetime
        """
        self.__expires_at = value

    @property
    def description(self):
        """Возвращает description модели InvoiceResponse.

        :return: description модели InvoiceResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """Устанавливает description модели InvoiceResponse.

        :param value: description модели InvoiceResponse.
        :type value: str
        """
        self.__description = value

    @property
    def cancellation_details(self):
        """Возвращает cancellation_details модели Invoice.

        :return: cancellation_details модели Invoice.
        :rtype: CancellationDetails
        """
        return self.__cancellation_details

    @cancellation_details.setter
    def cancellation_details(self, value):
        """Устанавливает cancellation_details модели Invoice.

        :param value: cancellation_details модели Invoice.
        :type value: CancellationDetails
        """
        self.__cancellation_details = CancellationDetails(value)

    @property
    def metadata(self):
        """Возвращает metadata модели InvoiceResponse.

        :return: metadata модели InvoiceResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели InvoiceResponse.

        :param value: metadata модели InvoiceResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

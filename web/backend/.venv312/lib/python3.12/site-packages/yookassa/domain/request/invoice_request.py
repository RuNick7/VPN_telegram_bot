# coding: utf-8
import datetime

from yookassa.domain.common import BaseObject, RequestObject
from yookassa.domain.models.invoice import LineItem
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod
from yookassa.domain.models.invoice_data.delivery_method_factory import DeliveryMethodFactory
from yookassa.domain.models.invoice_data.request.payment_data import PaymentData

DESCRIPTION_MAX_LENGTH = 128


class InvoiceRequest(RequestObject):
    """Класс, представляющий модель InvoiceRequest."""  # noqa: E501

    __payment_data = None
    """Данные для проведения платежа по выставленному счету."""  # noqa: E501

    __cart = None
    """Корзина заказа — список товаров или услуг, который отобразится на странице счета перед оплатой."""  # noqa: E501

    __delivery_method_data = None
    """
    Данные о способе доставки счета пользователю.
    Доступен только один способ — самостоятельная доставка: ЮKassa возвращает вам ссылку на счет, и вы передаете ее пользователю любым удобным для вас способом.
    """  # noqa: E501

    __expires_at = None
    """Срок действия счета — дата и время, до которых можно оплатить выставленный счет. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2024-10-18T10:51:18.139Z` """  # noqa: E501

    __locale = None
    """
    Язык интерфейса, писем и смс, которые будет видеть или получать пользователь.
    Формат соответствует [ISO/IEC 15897](https://en.wikipedia.org/wiki/Locale_(computer_software)).
    Возможные значения: ru_RU, en_US. Регистр важен.
    """

    __description = None
    """Описание выставленного счета (не более 128 символов), которое вы увидите в личном кабинете ЮKassa, а пользователь на странице счета. Например: «Счет на оплату по договору 37». """  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def payment_data(self):
        """Возвращает payment_data модели InvoiceRequest.

        :return: payment_data модели InvoiceRequest.
        :rtype: PaymentData
        """
        return self.__payment_data

    @payment_data.setter
    def payment_data(self, value):
        """Устанавливает payment_data модели InvoiceRequest.

        :param value: payment_data модели InvoiceRequest.
        :type value: PaymentData
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `payment_data`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__payment_data = PaymentData(value)
        elif isinstance(value, PaymentData):
            self.__payment_data = value
        else:
            raise TypeError('Invalid payment_data data type in InvoiceRequest.payment_data')

    @property
    def cart(self):
        """Возвращает cart модели InvoiceRequest.

        :return: cart модели InvoiceRequest.
        :rtype: list[LineItem]
        """
        return self.__cart

    @cart.setter
    def cart(self, value):
        """Устанавливает cart модели InvoiceRequest.

        :param value: cart модели InvoiceRequest.
        :type value: list[LineItem]
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `cart`, must not be `None`")  # noqa: E501
        if isinstance(value, list):
            cart_array = []
            for cart_data in value:
                if isinstance(cart_data, dict):
                    cart_array.append(LineItem(cart_data))
                elif isinstance(cart_data, LineItem):
                    cart_array.append(cart_data)
                else:
                    raise TypeError('Invalid cart data type in InvoiceRequest.cart')

            self.__cart = cart_array
        else:
            raise TypeError('Invalid cart value type in InvoiceRequest')

    @property
    def delivery_method_data(self):
        """Возвращает delivery_method_data модели InvoiceRequest.

        :return: delivery_method_data модели InvoiceRequest.
        :rtype: DeliveryMethod
        """
        return self.__delivery_method_data

    @delivery_method_data.setter
    def delivery_method_data(self, value):
        """Устанавливает delivery_method_data модели InvoiceRequest.

        :param value: delivery_method_data модели InvoiceRequest.
        :type value: DeliveryMethod
        """
        if isinstance(value, dict):
            self.__delivery_method_data = DeliveryMethodFactory().create(value, self.context())
        elif isinstance(value, DeliveryMethod):
            self.__delivery_method_data = value
        else:
            raise TypeError('Invalid delivery_method_data data type in InvoiceRequest.delivery_method_data')

    @property
    def expires_at(self):
        """Возвращает expires_at модели InvoiceRequest.

        :return: expires_at модели InvoiceRequest.
        :rtype: datetime
        """
        return self.__expires_at

    @expires_at.setter
    def expires_at(self, value):
        """Устанавливает expires_at модели InvoiceRequest.

        :param value: expires_at модели InvoiceRequest.
        :type value: datetime
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `expires_at`, must not be `None`")  # noqa: E501
        self.__expires_at = value

    @property
    def locale(self):
        """Возвращает locale модели InvoiceRequest.

        :return: locale модели InvoiceRequest.
        :rtype: str
        """
        return self.__locale

    @locale.setter
    def locale(self, value):
        """Устанавливает locale модели InvoiceRequest.

        :param value: locale модели InvoiceRequest.
        :type value: str
        """
        self.__locale = value

    @property
    def description(self):
        """Возвращает description модели InvoiceRequest.

        :return: description модели InvoiceRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """Устанавливает description модели InvoiceRequest.

        :param value: description модели InvoiceRequest.
        :type value: str
        """
        if value is not None and len(value) > DESCRIPTION_MAX_LENGTH:
            raise ValueError("Invalid value for `description`, length must be less than or equal to `{}`".format(DESCRIPTION_MAX_LENGTH))  # noqa: E501
        self.__description = value

    @property
    def metadata(self):
        """Возвращает metadata модели InvoiceRequest.

        :return: metadata модели InvoiceRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели InvoiceRequest.

        :param value: metadata модели InvoiceRequest.
        :type value: dict[str, str]
        """
        self.__metadata = value

    def validate(self):
        """
        Влидация данных модели PaymentRequest.
        """
        if self.payment_data is None:
            self.__set_validation_error('Payment data not specified')

        amount = self.payment_data.amount
        if amount is None:
            self.__set_validation_error('Payment amount not specified')

        if amount.value <= 0.0:
            self.__set_validation_error('Invalid payment amount value: ' + str(amount.value))

        if self.payment_data.receipt is not None and self.payment_data.receipt.has_items:
            if self.payment_data.receipt.customer is None:
                self.__set_validation_error('Customer is empty in InvoiceRequest.payment_data.receipt')

            email = self.payment_data.receipt.customer.email
            phone = self.payment_data.receipt.customer.phone
            if not email and not phone:
                self.__set_validation_error('Both email and phone values are empty in InvoiceRequest.payment_data.receipt.customer')

            if self.payment_data.receipt.tax_system_code is None:
                for item in self.payment_data.receipt.items:
                    if item.vat_code is None:
                        self.__set_validation_error('Item vat_code and receipt tax_system_id not specified in InvoiceRequest.payment_data.receipt')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели PaymentRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

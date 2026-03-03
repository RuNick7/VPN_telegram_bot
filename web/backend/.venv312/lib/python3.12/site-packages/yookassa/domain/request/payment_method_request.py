# coding: utf-8
from yookassa.domain.common import RequestObject
from yookassa.domain.models.confirmation.request.confirmation_request import ConfirmationRequest
from yookassa.domain.models.payment_data.request.credit_card import CreditCard
from yookassa.domain.models.payment_method.payment_method_confirmation_factory import PaymentMethodConfirmationFactory
from yookassa.domain.models.payment_method.request.payment_method_holder import PaymentMethodHolder


class PaymentMethodRequest(RequestObject):
    """Данные для проверки и сохранения способа оплаты."""  # noqa: E501

    __type = None
    """Код способа оплаты. Возможное значение: * ~`bank_card` — банковская карта."""  # noqa: E501

    __card = None
    """Данные банковской карты."""

    __holder = None
    """Данные магазина, для которого сохраняется способ оплаты."""

    __client_ip = None
    """IPv4 или IPv6-адрес пользователя. Если не указан, используется IP-адрес TCP-подключения."""  # noqa: E501

    __confirmation = None
    """Данные, необходимые для инициирования сценария подтверждения привязки."""  # noqa: E501

    @property
    def type(self):
        """Возвращает type модели PaymentMethodRequest.

        :return: type модели PaymentMethodRequest.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """Устанавливает type модели PaymentMethodRequest.

        :param value: type модели PaymentMethodRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = str(value)

    @property
    def card(self):
        """Возвращает card модели PaymentMethodResponse.

        :return: card модели PaymentMethodResponse.
        :rtype: CreditCard
        """
        return self.__card

    @card.setter
    def card(self, value):
        """Устанавливает card модели PaymentMethodResponse.

        :param value: card модели PaymentMethodResponse.
        :type value: CreditCard
        """
        if isinstance(value, dict):
            self.__card = CreditCard(value)
        elif isinstance(value, CreditCard):
            self.__card = value
        else:
            raise TypeError('Invalid card value type')

    @property
    def holder(self):
        """Возвращает holder модели PaymentMethodRequest.

        :return: holder модели PaymentMethodRequest.
        :rtype: PaymentMethodHolder
        """
        return self.__holder

    @holder.setter
    def holder(self, value):
        """Устанавливает holder модели PaymentMethodRequest.

        :param value: holder модели PaymentMethodRequest.
        :type value: PaymentMethodHolder
        """
        if isinstance(value, dict):
            self.__holder = PaymentMethodHolder(value)
        elif isinstance(value, PaymentMethodHolder):
            self.__holder = value
        else:
            raise TypeError('Invalid holder value type')

    @property
    def client_ip(self):
        """Возвращает client_ip модели PaymentMethodRequest.

        :return: client_ip модели PaymentMethodRequest.
        :rtype: str
        """
        return self.__client_ip

    @client_ip.setter
    def client_ip(self, value):
        """Устанавливает client_ip модели PaymentMethodRequest.

        :param value: client_ip модели PaymentMethodRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__client_ip = cast_value

    @property
    def confirmation(self):
        """Возвращает confirmation модели PaymentMethodRequest.

        :return: confirmation модели PaymentMethodRequest.
        :rtype: ConfirmationRequest
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """Устанавливает confirmation модели PaymentMethodRequest.

        :param value: confirmation модели PaymentMethodRequest.
        :type value: ConfirmationRequest
        """
        if isinstance(value, dict):
            self.__confirmation = PaymentMethodConfirmationFactory().create(value, self.context())
        elif isinstance(value, ConfirmationRequest):
            self.__confirmation = value
        else:
            raise TypeError('Invalid confirmation data type in PaymentMethodRequest.confirmation')

    def validate(self):
        """
        Валидация данных модели PaymentMethodRequest.
        """
        if not self.type:
            self.__set_validation_error('Payment method type not specified')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели PaymentMethodRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

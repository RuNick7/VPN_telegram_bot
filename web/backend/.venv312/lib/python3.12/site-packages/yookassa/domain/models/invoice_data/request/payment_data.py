# coding: utf-8

from yookassa.domain.common import BaseObject
from yookassa.domain.models import Receipt, Amount, Recipient


class PaymentData(BaseObject):
    """Данные для проведения платежа по выставленному счету."""  # noqa: E501

    __amount = None
    """
    Сумма платежа. Должна укладываться в [лимиты](/docs/support/payments/limits). Сумма указывается с кодом валюты.
    Если вы разделяете потоки платежей, валюта платежа должна соответствовать валюте субаккаунта (`recipient.gateway_id`), если не разделяете — валюте аккаунта `shopId` в личном кабинете)
    """  # noqa: E501

    __receipt = None
    """
    Данные для формирования чека.
    Необходимо передавать в этих случаях:
    - вы компания или ИП и для оплаты с соблюдением требований 54-ФЗ используете [Чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics);
    - вы компания или ИП, для оплаты с соблюдением требований 54-ФЗ используете [стороннюю онлайн-кассу](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) и отправляете данные для чеков по одному из сценариев: [Платеж и чек одновременно](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-and-receipt) или [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt);
    - вы самозанятый и используете решение ЮKassa для [автоотправки чеков](https://yookassa.ru/developers/payment-acceptance/receipts/self-employed/basics).
    """  # noqa: E501

    __recipient = None
    """"""  # noqa: E501

    __save_payment_method = None
    """Сохранение платежных данных для проведения [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments). Возможные значения:  * ~`true` — сохранить способ оплаты (сохранить платежные данные); * ~`false` — провести платеж без сохранения способа оплаты.  Доступно только после согласования с менеджером ЮKassa. """  # noqa: E501

    __capture = None
    """[Автоматический прием](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-true) поступившего платежа. Возможные значения:  * ~`true` — оплата списывается сразу (платеж в одну стадию); * ~`false` — оплата холдируется и списывается по вашему запросу ([платеж в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)).  По умолчанию ~`false`. """  # noqa: E501

    __client_ip = None
    """IPv4 или IPv6-адрес пользователя. Если не указан, используется IP-адрес TCP-подключения."""  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов), которое вы увидите в личном кабинете ЮKassa, а пользователь — при оплате. Например: «Оплата заказа № 72 для user@yoomoney.ru». """  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def amount(self):
        """Возвращает amount модели PaymentData.

        :return: amount модели PaymentData.
        :rtype: PaymentDataAmount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """Устанавливает amount модели PaymentData.

        :param value: amount модели PaymentData.
        :type value: PaymentDataAmount
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `amount`, must not be `None`")  # noqa: E501
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount data type in PaymentData.amount')

    @property
    def receipt(self):
        """Возвращает receipt модели PaymentData.

        :return: receipt модели PaymentData.
        :rtype: ReceiptData
        """
        return self.__receipt

    @receipt.setter
    def receipt(self, value):
        """Устанавливает receipt модели PaymentData.

        :param value: receipt модели PaymentData.
        :type value: ReceiptData
        """
        if isinstance(value, dict):
            self.__receipt = Receipt(value)
        elif isinstance(value, Receipt):
            self.__receipt = value
        else:
            raise TypeError('Invalid receipt data type in PaymentData.receipt')

    @property
    def recipient(self):
        """Возвращает recipient модели PaymentData.

        :return: recipient модели PaymentData.
        :rtype: Recipient
        """
        return self.__recipient

    @recipient.setter
    def recipient(self, value):
        """Устанавливает recipient модели PaymentData.

        :param value: recipient модели PaymentData.
        :type value: Recipient
        """
        if isinstance(value, dict):
            self.__recipient = Recipient(value)
        elif isinstance(value, Recipient):
            self.__recipient = value
        else:
            raise TypeError('Invalid recipient data type in PaymentData.recipient')

    @property
    def save_payment_method(self):
        """Возвращает save_payment_method модели PaymentData.

        :return: save_payment_method модели PaymentData.
        :rtype: bool
        """
        return self.__save_payment_method

    @save_payment_method.setter
    def save_payment_method(self, value):
        """Устанавливает save_payment_method модели PaymentData.

        :param value: save_payment_method модели PaymentData.
        :type value: bool
        """
        self.__save_payment_method = value

    @property
    def capture(self):
        """Возвращает capture модели PaymentData.

        :return: capture модели PaymentData.
        :rtype: bool
        """
        return self.__capture

    @capture.setter
    def capture(self, value):
        """Устанавливает capture модели PaymentData.

        :param value: capture модели PaymentData.
        :type value: bool
        """
        self.__capture = value

    @property
    def client_ip(self):
        """Возвращает client_ip модели PaymentData.

        :return: client_ip модели PaymentData.
        :rtype: str
        """
        return self.__client_ip

    @client_ip.setter
    def client_ip(self, value):
        """Устанавливает client_ip модели PaymentData.

        :param value: client_ip модели PaymentData.
        :type value: str
        """
        self.__client_ip = value

    @property
    def description(self):
        """Возвращает description модели PaymentData.

        :return: description модели PaymentData.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """Устанавливает description модели PaymentData.

        :param value: description модели PaymentData.
        :type value: str
        """
        if value is not None and len(value) > 128:
            raise ValueError("Invalid value for `description`, length must be less than or equal to `128`")  # noqa: E501
        self.__description = value

    @property
    def metadata(self):
        """Возвращает metadata модели PaymentData.

        :return: metadata модели PaymentData.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """Устанавливает metadata модели PaymentData.

        :param value: metadata модели PaymentData.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value



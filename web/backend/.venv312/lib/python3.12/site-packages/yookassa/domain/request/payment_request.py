# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.amount import Amount
from yookassa.domain.models.confirmation.confirmation import Confirmation
from yookassa.domain.models.confirmation.confirmation_factory import ConfirmationFactory
from yookassa.domain.models.deal import PaymentDealInfo
from yookassa.domain.models.payment_data.payment_data import PaymentData
from yookassa.domain.models.payment_data.payment_data_factory import PaymentDataFactory
from yookassa.domain.models.payment_data.payment_order.payment_order import PaymentOrder
from yookassa.domain.models.payment_data.payment_order.payment_order_factory import PaymentOrderFactory
from yookassa.domain.models.payment_data.recipient import Recipient
from yookassa.domain.models.payment_data.request.airline import Airline
from yookassa.domain.models.payment_data.request.fraud_data import FraudData
from yookassa.domain.models.payment_data.request.payment_data_bank_card import PaymentDataBankCard
from yookassa.domain.models.payment_data.request.receiver import Receiver
from yookassa.domain.models.payment_data.request.receiver_factory import ReceiverFactory
from yookassa.domain.models.receipt import Receipt
from yookassa.domain.models.payment_data.statement import Statement, StatementFactory
from yookassa.domain.models.transfer import Transfer

DESCRIPTION_MAX_LENGTH = 128
MERCHANT_CUSTOMER_MAX_LENGTH = 200


class PaymentRequest(RequestObject):
    """
    Объект запроса к API на проведение нового платежа.
    """  # noqa: E501

    __amount = None
    """
    Сумма платежа. Иногда партнеры ЮKassa берут с пользователя дополнительную комиссию, которая не входит в эту сумму.
    Сумма указывается с кодом валюты. Если вы разделяете потоки платежей, валюта платежа должна соответствовать валюте субаккаунта (`recipient.gateway_id`), если не разделяете — валюте аккаунта `shopId` в личном кабинете).
    """  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов), которое вы увидите в личном кабинете ЮKassa, а пользователь — при оплате. Например: «Оплата заказа № 72 для user@yoomoney.ru». """  # noqa: E501

    __receipt = None
    """Данные фискального чека 54-ФЗ."""  # noqa: E501

    __recipient = None
    """Получатель платежа, если задан."""  # noqa: E501

    __payment_token = None
    """Одноразовый токен для проведения оплаты, сформированный с помощью %[Checkout.js](/developers/payment-acceptance/integration-scenarios/checkout-js/basics) или %[мобильного SDK](/developers/payment-acceptance/integration-scenarios/mobile-sdks/basics). """  # noqa: E501

    __payment_method_id = None
    """Идентификатор %[сохраненного способа оплаты](/developers/payment-acceptance/scenario-extensions/recurring-payments)."""  # noqa: E501

    __payment_method_data = None
    """Данные используемые для создания метода оплаты."""  # noqa: E501

    __confirmation = None
    """Способ подтверждения платежа."""  # noqa: E501

    __save_payment_method = None
    """Сохранение платежных данных (с их помощью можно проводить повторные %[безакцептные списания](/developers/payment-acceptance/scenario-extensions/recurring-payments)). Значение ~`true` инициирует создание многоразового `payment_method`."""  # noqa: E501

    __capture = None
    """<p>%[Автоматический прием](/developers/payment-acceptance/getting-started/payment-process#capture-true) поступившего платежа.</p> """  # noqa: E501

    __client_ip = None
    """IPv4 или IPv6-адрес пользователя. Если не указан, используется IP-адрес TCP-подключения."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __airline = None
    """Объект с данными для продажи авиабилетов."""  # noqa: E501

    __transfers = []
    """Данные о распределении денег — сколько и в какой магазин нужно перевести. Необходимо передавать, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-payments/basics)."""  # noqa: E501

    __deal = None
    """Данные о сделке, в составе которой проходит платеж."""  # noqa: E501

    __fraud_data = None
    """Информация для проверки операции на мошенничество."""  # noqa: E501

    __merchant_customer_id = None
    """Идентификатор покупателя в вашей системе, например электронная почта или номер телефона."""  # noqa: E501

    __receiver = None
    """Реквизиты получателя оплаты при пополнении электронного кошелька, банковского счета или баланса телефона"""  # noqa: E501

    __payment_order = None
    """Платежное поручение — распоряжение на перевод банку для оплаты жилищно-коммунальных услуг (ЖКУ), сведения о платеже для регистрации в ГИС ЖКХ."""

    __statements = []
    """Данные для отправки справки. Необходимо передавать, если вы хотите, чтобы после оплаты пользователь получил справку. Сейчас доступен один тип справок — квитанция по платежу. Это информация об успешном платеже, которую ЮKassa отправляет на электронную почту пользователя. Квитанцию можно отправить, если оплата прошла с банковской карты, через SberPay или СБП. """  # noqa: E501

    @property
    def amount(self):
        """
        Возвращает amount модели PaymentRequest.

        :return: amount модели PaymentRequest.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели PaymentRequest.

        :param value: amount модели PaymentRequest.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def description(self):
        """
        Возвращает description модели PaymentRequest.

        :return: description модели PaymentRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели PaymentRequest.

        :param value: description модели PaymentRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            if len(cast_value) <= DESCRIPTION_MAX_LENGTH:
                self.__description = cast_value
            else:
                raise ValueError('The value of the description parameter is too long. Max length is {}'.format(DESCRIPTION_MAX_LENGTH))  # noqa: E501

    @property
    def receipt(self):
        """
        Возвращает receipt модели PaymentRequest.

        :return: receipt модели PaymentRequest.
        :rtype: Receipt
        """
        return self.__receipt

    @receipt.setter
    def receipt(self, value):
        """
        Устанавливает receipt модели PaymentRequest.

        :param value: receipt модели PaymentRequest.
        :type value: Receipt
        """
        if isinstance(value, dict):
            self.__receipt = Receipt(value)
        elif isinstance(value, Receipt):
            self.__receipt = value
        else:
            raise TypeError('Invalid receipt_request value type')

    @property
    def recipient(self):
        """
        Возвращает recipient модели PaymentRequest.

        :return: recipient модели PaymentRequest.
        :rtype: Recipient
        """
        return self.__recipient

    @recipient.setter
    def recipient(self, value):
        """
        Устанавливает recipient модели PaymentRequest.

        :param value: recipient модели PaymentRequest.
        :type value: Recipient
        """
        if isinstance(value, dict):
            self.__recipient = Recipient(value)
        elif isinstance(value, Recipient):
            self.__recipient = value
        else:
            raise TypeError('Invalid recipient value type')

    @property
    def payment_token(self):
        """
        Возвращает payment_token модели PaymentRequest.

        :return: payment_token модели PaymentRequest.
        :rtype: str
        """
        return self.__payment_token

    @payment_token.setter
    def payment_token(self, value):
        """
        Устанавливает payment_token модели PaymentRequest.

        :param value: payment_token модели PaymentRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__payment_token = cast_value
        else:
            raise TypeError('Invalid payment_token value')

    @property
    def payment_method_id(self):
        """
        Возвращает payment_method_id модели PaymentRequest.

        :return: payment_method_id модели PaymentRequest.
        :rtype: str
        """
        return self.__payment_method_id

    @payment_method_id.setter
    def payment_method_id(self, value):
        """
        Устанавливает payment_method_id модели PaymentRequest.

        :param value: payment_method_id модели PaymentRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            self.__payment_method_id = cast_value

    @property
    def payment_method_data(self):
        """
        Возвращает payment_method_data модели PaymentRequest.

        :return: payment_method_data модели PaymentRequest.
        :rtype: PaymentData
        """
        return self.__payment_method_data

    @payment_method_data.setter
    def payment_method_data(self, value):
        """
        Устанавливает payment_method_data модели PaymentRequest.

        :param value: payment_method_data модели PaymentRequest.
        :type value: PaymentData
        """
        if isinstance(value, dict):
            self.__payment_method_data = PaymentDataFactory().create(value, self.context())
        elif isinstance(value, PaymentData):
            self.__payment_method_data = value
        else:
            raise TypeError('Invalid payment_method_data type')

    @property
    def confirmation(self):
        """
        Возвращает confirmation модели PaymentRequest.

        :return: confirmation модели PaymentRequest.
        :rtype: Confirmation
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """
        Устанавливает confirmation модели PaymentRequest.

        :param value: confirmation модели PaymentRequest.
        :type value: Confirmation
        """
        if isinstance(value, dict):
            self.__confirmation = ConfirmationFactory().create(value, self.context())
        elif isinstance(value, Confirmation):
            self.__confirmation = value
        else:
            raise TypeError('Invalid confirmation type')

    @property
    def save_payment_method(self):
        """
        Возвращает save_payment_method модели PaymentRequest.

        :return: save_payment_method модели PaymentRequest.
        :rtype: bool
        """
        return self.__save_payment_method

    @save_payment_method.setter
    def save_payment_method(self, value):
        """
        Устанавливает save_payment_method модели PaymentRequest.

        :param value: save_payment_method модели PaymentRequest.
        :type value: bool
        """
        self.__save_payment_method = bool(value)

    @property
    def capture(self):
        """
        Возвращает capture модели PaymentRequest.

        :return: capture модели PaymentRequest.
        :rtype: bool
        """
        return self.__capture

    @capture.setter
    def capture(self, value):
        """
        Устанавливает capture модели PaymentRequest.

        :param value: capture модели PaymentRequest.
        :type value: bool
        """
        self.__capture = bool(value)

    @property
    def client_ip(self):
        """
        Возвращает client_ip модели PaymentRequest.

        :return: client_ip модели PaymentRequest.
        :rtype: str
        """
        return self.__client_ip

    @client_ip.setter
    def client_ip(self, value):
        """
        Устанавливает client_ip модели PaymentRequest.

        :param value: client_ip модели PaymentRequest.
        :type value: str
        """
        self.__client_ip = str(value)

    @property
    def airline(self):
        """
        Возвращает airline модели PaymentRequest.

        :return: airline модели PaymentRequest.
        :rtype: Airline
        """
        return self.__airline

    @airline.setter
    def airline(self, value):
        """
        Устанавливает airline модели PaymentRequest.

        :param value: airline модели PaymentRequest.
        :type value: Airline
        """
        if isinstance(value, dict):
            self.__airline = Airline(value)
        elif isinstance(value, Airline):
            self.__airline = value
        else:
            raise TypeError('Invalid airline type')

    @property
    def metadata(self):
        """
        Возвращает metadata модели PaymentRequest.

        :return: metadata модели PaymentRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PaymentRequest.

        :param value: metadata модели PaymentRequest.
        :type value: dict[str, str]
        """
        if type(value) is dict:
            self.__metadata = value

    @property
    def transfers(self):
        """
        Возвращает transfers модели PaymentRequest.

        :return: transfers модели PaymentRequest.
        :rtype: list[Transfer]
        """
        return self.__transfers

    @transfers.setter
    def transfers(self, value):
        """
        Устанавливает transfers модели PaymentRequest.

        :param value: transfers модели PaymentRequest.
        :type value: list[Transfer]
        """
        if isinstance(value, list):
            self.__transfers = [Transfer(item) for item in value]
        elif value is None:
            self.__transfers = []
        else:
            raise TypeError('Invalid transfers data type in payment_request.transfers')

    @property
    def deal(self):
        """
        Возвращает deal модели PaymentRequest.

        :return: deal модели PaymentRequest.
        :rtype: PaymentDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели PaymentRequest.

        :param value: deal модели PaymentRequest.
        :type value: PaymentDealInfo
        """
        if isinstance(value, dict):
            self.__deal = PaymentDealInfo(value)
        elif isinstance(value, PaymentDealInfo):
            self.__deal = value
        else:
            raise TypeError('Invalid deal type')

    @property
    def fraud_data(self):
        """
        Возвращает fraud_data модели PaymentRequest.
        Больше не поддерживается. Вместо него нужно использовать `receiver`

        :return: fraud_data модели PaymentRequest.
        :rtype: FraudData
        """
        return self.__fraud_data

    @fraud_data.setter
    def fraud_data(self, value):
        """
        Устанавливает fraud_data модели PaymentRequest.
        Больше не поддерживается. Вместо него нужно использовать `receiver`

        :param value: fraud_data модели PaymentRequest.
        :type value: FraudData
        """
        if isinstance(value, dict):
            self.__fraud_data = FraudData(value)
        elif isinstance(value, FraudData):
            self.__fraud_data = value
        else:
            raise TypeError('Invalid fraud_data type in payment_request.fraud_data')

    @property
    def merchant_customer_id(self):
        """
        Возвращает merchant_customer_id модели PaymentRequest.

        :return: merchant_customer_id модели PaymentRequest.
        :rtype: str
        """
        return self.__merchant_customer_id

    @merchant_customer_id.setter
    def merchant_customer_id(self, value):
        """
        Устанавливает merchant_customer_id модели PaymentRequest.

        :param value: merchant_customer_id модели PaymentRequest.
        :type value: str
        """
        cast_value = str(value)
        if cast_value:
            if len(cast_value) <= MERCHANT_CUSTOMER_MAX_LENGTH:
                self.__merchant_customer_id = cast_value
            else:
                raise ValueError('The value of the merchant_customer_id parameter is too long. Max length is {}'.format(MERCHANT_CUSTOMER_MAX_LENGTH))  # noqa: E501

    @property
    def receiver(self):
        """Возвращает receiver модели PaymentRequest.

        :return: receiver модели PaymentRequest.
        :rtype: CreatePaymentRequestReceiver
        """
        return self.__receiver

    @receiver.setter
    def receiver(self, value):
        """Устанавливает receiver модели PaymentRequest.

        :param value: receiver модели PaymentRequest.
        :type value: Receiver
        """
        if isinstance(value, dict):
            self.__receiver = ReceiverFactory().create(value, self.context())
        elif isinstance(value, Receiver):
            self.__receiver = value
        else:
            raise TypeError('Invalid receiver type')

    @property
    def payment_order(self):
        """Возвращает payment_order модели PaymentRequest.

        :return: payment_order модели PaymentRequest.
        :rtype: PaymentOrder
        """
        return self.__payment_order

    @payment_order.setter
    def payment_order(self, value):
        """Устанавливает payment_order модели PaymentRequest.

        :param value: payment_order модели PaymentRequest.
        :type value: PaymentOrder
        """
        if isinstance(value, dict):
            self.__payment_order = PaymentOrderFactory().create(value, self.context())
        elif isinstance(value, PaymentOrder):
            self.__payment_order = value
        else:
            raise TypeError('Invalid payment_order type')

    @property
    def statements(self):
        """Возвращает statements модели PaymentRequest.

        :return: statements модели PaymentRequest.
        :rtype: list[Statement]
        """
        return self.__statements

    @statements.setter
    def statements(self, value):
        """Устанавливает statements модели PaymentRequest.

        :param value: statements модели PaymentRequest.
        :type value: list[Statement]
        """
        if value is None:
            self.__statements = []
        elif isinstance(value, list):
            self.__statements = []
            for item in value:
                if isinstance(item, dict):
                    self.__statements.append(StatementFactory().create(item, self.context()))
                elif isinstance(item, Statement):
                    self.__statements.append(item)
                else:
                    raise TypeError(f'Invalid statement item type: {type(item)}')
        else:
            raise TypeError('Invalid statements data type in payment_request.statements')

    def validate(self):
        """
        Влидация данных модели PaymentRequest.
        """
        amount = self.amount
        if amount is None:
            self.__set_validation_error('Payment amount not specified')

        if amount.value <= 0.0:
            self.__set_validation_error('Invalid payment amount value: ' + str(amount.value))

        if self.receipt is not None and self.receipt.has_items:
            if self.receipt.customer is None:
                self.__set_validation_error('Customer is empty in PaymentRequest.receipt')

            email = self.receipt.customer.email
            phone = self.receipt.customer.phone
            if not email and not phone:
                self.__set_validation_error('Both email and phone values are empty in PaymentRequest.receipt.customer')

            if self.receipt.tax_system_code is None:
                for item in self.receipt.items:
                    if item.vat_code is None:
                        self.__set_validation_error('Item vat_code and receipt tax_system_id not specified')

        if self.payment_token:
            if self.payment_method_id:
                self.__set_validation_error('Both payment_token and payment_method_id values are specified')

            if self.payment_method_data:
                self.__set_validation_error('Both payment_token and payment_data values are specified')

        elif self.payment_method_id:
            if self.payment_method_data:
                self.__set_validation_error('Both payment_method_id and payment_data values are specified')

        if self.payment_method_data and isinstance(self.payment_method_data, PaymentDataBankCard) \
                and self.payment_method_data.card is not None:
            # Get current date with an offset.
            # Why? Because expiration is relative to the transaction
            # processor's timezone, which we don't know. 1 day allowance will
            # prevent any sorts of false negatives, leaving a small
            # less-than-day window for the unlikely false positives.
            # Account for GMT-12 to GMT+14 difference
            # + DST: https://www.timeanddate.com/time/dst/
            date_now = datetime.now() - timedelta(hours=26 + 1)

            # Expiry date is "valid thru", meaning it is valid until the last
            # second of the last day of the month in the date.
            date_expiry = datetime(
                year=int(self.payment_method_data.card.expiry_year),
                month=int(self.payment_method_data.card.expiry_month),
                day=1
            )
            # A little trick to add a month
            date_expiry += timedelta(days=31)
            date_expiry -= timedelta(days=date_expiry.day - 1)

            if date_now >= date_expiry:
                self.__set_validation_error('Card expired')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели PaymentRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

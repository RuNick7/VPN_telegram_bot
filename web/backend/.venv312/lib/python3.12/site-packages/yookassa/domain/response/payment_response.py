# -*- coding: utf-8 -*-
from yookassa.domain.common import ResponseObject, PaymentMethodType
from yookassa.domain.models import Amount, AuthorizationDetails, CancellationDetails, Recipient
from yookassa.domain.models.confirmation.confirmation_factory import ConfirmationFactory
from yookassa.domain.models.deal import PaymentDealInfo
from yookassa.domain.models.payment_data.payment_data_class_map import PaymentDataClassMap
from yookassa.domain.models.payment_data.payment_data_factory import PaymentDataFactory
from yookassa.domain.models.payment_data.payment_invoice_details import PaymentInvoiceDetails
from yookassa.domain.response.transfer_response import TransferResponse


class PaymentResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе конкретного платежа.
    """  # noqa: E501

    __id = None
    """Идентификатор платежа в ЮKassa."""  # noqa: E501

    __status = None
    """Текущее состояние платежа."""  # noqa: E501

    __amount = None
    """Сумма заказа."""  # noqa: E501

    __income_amount = None
    """Сумма платежа, которую получит магазин."""  # noqa: E501

    __description = None
    """Описание транзакции (не более 128 символов), которое вы увидите в личном кабинете ЮKassa, а пользователь — при оплате. Например: «Оплата заказа № 72 для user@yoomoney.ru». """  # noqa: E501

    __recipient = None
    """Получатель платежа."""  # noqa: E501

    __payment_method = None
    """Способ проведения платежа."""  # noqa: E501

    __captured_at = None
    """Время подтверждения платежа. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). """  # noqa: E501

    __created_at = None
    """Время создания заказа. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __expires_at = None
    """Время, до которого вы можете бесплатно отменить или подтвердить платеж. В указанное время платеж в статусе ~`waiting_for_capture` будет автоматически отменен. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __confirmation = None
    """Выбранный способ подтверждения платежа. """  # noqa: E501

    __test = None
    """Признак тестовой операции."""  # noqa: E501

    __refunded_amount = None
    """Сумма возвращенных средств платежа."""  # noqa: E501

    __paid = None
    """Признак оплаты заказа."""  # noqa: E501

    __refundable = None
    """Возможность провести возврат по API."""  # noqa: E501

    __receipt_registration = None
    """Состояние регистрации фискального чека"""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __cancellation_details = None
    """Комментарий к отмене платежа."""  # noqa: E501

    __authorization_details = None
    """Данные об авторизации платежа."""  # noqa: E501

    __transfers = None
    """Данные о распределении денег — сколько и в какой магазин нужно перевести. Присутствует, если вы используете %[Сплитование платежей](/developers/solutions-for-platforms/split-PaymentResponses/basics)."""  # noqa: E501

    __deal = None
    """Данные о сделке, в составе которой проходит платеж."""  # noqa: E501

    __merchant_customer_id = None
    """Идентификатор покупателя в вашей системе, например электронная почта или номер телефона."""  # noqa: E501

    __invoice_details = None
    """Данные о выставленном счете, в рамках которого проведен платеж"""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PaymentResponse.

        :return: id модели PaymentResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PaymentResponse.

        :param value: id модели PaymentResponse.
        :type value: str
        """
        self.__id = value

    @property
    def status(self):
        """
        Возвращает status модели PaymentResponse.

        :return: status модели PaymentResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели PaymentResponse.

        :param value: status модели PaymentResponse.
        :type value: str
        """
        self.__status = value

    @property
    def amount(self):
        """
        Возвращает amount модели PaymentResponse.

        :return: amount модели PaymentResponse.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """
        Устанавливает amount модели PaymentResponse.

        :param value: amount модели PaymentResponse.
        :type value: Amount
        """
        self.__amount = Amount(value)

    @property
    def income_amount(self):
        """
        Возвращает income_amount модели PaymentResponse.

        :return: income_amount модели PaymentResponse.
        :rtype: Amount
        """
        return self.__income_amount

    @income_amount.setter
    def income_amount(self, value):
        """
        Устанавливает income_amount модели PaymentResponse.

        :param value: income_amount модели PaymentResponse.
        :type value: Amount
        """
        self.__income_amount = Amount(value)

    @property
    def description(self):
        """
        Возвращает description модели PaymentResponse.

        :return: description модели PaymentResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели PaymentResponse.

        :param value: description модели PaymentResponse.
        :type value: str
        """
        self.__description = value

    @property
    def recipient(self):
        """
        Возвращает recipient модели PaymentResponse.

        :return: recipient модели PaymentResponse.
        :rtype: Recipient
        """
        return self.__recipient

    @recipient.setter
    def recipient(self, value):
        """
        Устанавливает recipient модели PaymentResponse.

        :param value: recipient модели PaymentResponse.
        :type value: Recipient
        """
        self.__recipient = Recipient(value)

    @property
    def payment_method(self):
        """
        Возвращает payment_method модели PaymentResponse.

        :return: payment_method модели PaymentResponse.
        :rtype: PaymentPaymentMethod
        """
        return self.__payment_method

    @payment_method.setter
    def payment_method(self, value):
        """
        Устанавливает payment_method модели PaymentResponse.

        :param value: payment_method модели PaymentResponse.
        :type value: PaymentData
        """
        if isinstance(value, dict) and 'type' in value and value['type'] not in PaymentDataClassMap().response:
            value['type'] = PaymentMethodType.UNKNOWN
        self.__payment_method = PaymentDataFactory().create(value, self.context())

    @property
    def captured_at(self):
        """
        Возвращает captured_at модели PaymentResponse.

        :return: captured_at модели PaymentResponse.
        :rtype: datetime
        """
        return self.__captured_at

    @captured_at.setter
    def captured_at(self, value):
        """
        Устанавливает captured_at модели PaymentResponse.

        :param value: captured_at модели PaymentResponse.
        :type value: datetime
        """
        self.__captured_at = value

    @property
    def created_at(self):
        """
        Возвращает created_at модели PaymentResponse.

        :return: created_at модели PaymentResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели PaymentResponse.

        :param value: created_at модели PaymentResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def expires_at(self):
        """
        Возвращает expires_at модели PaymentResponse.

        :return: expires_at модели PaymentResponse.
        :rtype: datetime
        """
        return self.__expires_at

    @expires_at.setter
    def expires_at(self, value):
        """
        Устанавливает expires_at модели PaymentResponse.

        :param value: expires_at модели PaymentResponse.
        :type value: datetime
        """
        self.__expires_at = value

    @property
    def confirmation(self):
        """
        Возвращает confirmation модели PaymentResponse.

        :return: confirmation модели PaymentResponse.
        :rtype: ConfirmationRequest
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """
        Устанавливает confirmation модели PaymentResponse.

        :param value: confirmation модели PaymentResponse.
        :type value: ConfirmationRequest
        """
        self.__confirmation = ConfirmationFactory().create(value, self.context())

    @property
    def test(self):
        """
        Возвращает test модели PaymentResponse.

        :return: test модели PaymentResponse.
        :rtype: bool
        """
        return self.__test

    @test.setter
    def test(self, value):
        """
        Устанавливает test модели PaymentResponse.

        :param value: test модели PaymentResponse.
        :type value: bool
        """
        self.__test = bool(value)

    @property
    def refunded_amount(self):
        """
        Возвращает refunded_amount модели PaymentResponse.

        :return: refunded_amount модели PaymentResponse.
        :rtype: Amount
        """
        return self.__refunded_amount

    @refunded_amount.setter
    def refunded_amount(self, value):
        """
        Устанавливает refunded_amount модели PaymentResponse.

        :param value: refunded_amount модели PaymentResponse.
        :type value: Amount
        """
        self.__refunded_amount = Amount(value)

    @property
    def paid(self):
        """
        Возвращает paid модели PaymentResponse.

        :return: paid модели PaymentResponse.
        :rtype: bool
        """
        return self.__paid

    @paid.setter
    def paid(self, value):
        """
        Устанавливает paid модели PaymentResponse.

        :param value: paid модели PaymentResponse.
        :type value: bool
        """
        self.__paid = bool(value)

    @property
    def refundable(self):
        """
        Возвращает refundable модели PaymentResponse.

        :return: refundable модели PaymentResponse.
        :rtype: bool
        """
        return self.__refundable

    @refundable.setter
    def refundable(self, value):
        """
        Устанавливает refundable модели PaymentResponse.

        :param value: refundable модели PaymentResponse.
        :type value: bool
        """
        self.__refundable = bool(value)

    @property
    def receipt_registration(self):
        """
        Возвращает receipt_registration модели PaymentResponse.

        :return: receipt_registration модели PaymentResponse.
        :rtype: str
        """
        return self.__receipt_registration

    @receipt_registration.setter
    def receipt_registration(self, value):
        """
        Устанавливает receipt_registration модели PaymentResponse.

        :param value: receipt_registration модели PaymentResponse.
        :type value: str
        """
        self.__receipt_registration = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели PaymentResponse.

        :return: metadata модели PaymentResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PaymentResponse.

        :param value: metadata модели PaymentResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

    @property
    def cancellation_details(self):
        """
        Возвращает cancellation_details модели PaymentResponse.

        :return: cancellation_details модели PaymentResponse.
        :rtype: CancellationDetails
        """
        return self.__cancellation_details

    @cancellation_details.setter
    def cancellation_details(self, value):
        """
        Устанавливает cancellation_details модели PaymentResponse.

        :param value: cancellation_details модели PaymentResponse.
        :type value: CancellationDetails
        """
        self.__cancellation_details = CancellationDetails(value)

    @property
    def authorization_details(self):
        """
        Возвращает authorization_details модели PaymentResponse.

        :return: authorization_details модели PaymentResponse.
        :rtype: AuthorizationDetails
        """
        return self.__authorization_details

    @authorization_details.setter
    def authorization_details(self, value):
        """
        Устанавливает authorization_details модели PaymentResponse.

        :param value: authorization_details модели PaymentResponse.
        :type value: AuthorizationDetails
        """
        self.__authorization_details = AuthorizationDetails(value)

    @property
    def transfers(self):
        """
        Возвращает transfers модели PaymentResponse.

        :return: transfers модели PaymentResponse.
        :rtype: list[TransferResponse]
        """
        return self.__transfers

    @transfers.setter
    def transfers(self, value):
        """
        Устанавливает transfers модели PaymentResponse.

        :param value: transfers модели PaymentResponse.
        :type value: list[TransferResponse]
        """
        if isinstance(value, list):
            self.__transfers = [TransferResponse(item) for item in value]
        elif value is None:
            self.__transfers = value
        else:
            raise TypeError('Invalid transfers data type in payment_response.transfers')

    @property
    def deal(self):
        """
        Возвращает deal модели PaymentResponse.

        :return: deal модели PaymentResponse.
        :rtype: PaymentDealInfo
        """
        return self.__deal

    @deal.setter
    def deal(self, value):
        """
        Устанавливает deal модели PaymentResponse.

        :param value: deal модели PaymentResponse.
        :type value: PaymentDealInfo
        """
        self.__deal = PaymentDealInfo(value)

    @property
    def merchant_customer_id(self):
        """
        Возвращает merchant_customer_id модели PaymentResponse.

        :return: merchant_customer_id модели PaymentResponse.
        :rtype: str
        """
        return self.__merchant_customer_id

    @merchant_customer_id.setter
    def merchant_customer_id(self, value):
        """
        Устанавливает merchant_customer_id модели PaymentResponse.

        :param value: merchant_customer_id модели PaymentResponse.
        :type value: str
        """
        self.__merchant_customer_id = value

    @property
    def invoice_details(self):
        """Возвращает invoice_details модели Payment.

        :return: invoice_details модели Payment.
        :rtype: PaymentInvoiceDetails
        """
        return self.__invoice_details

    @invoice_details.setter
    def invoice_details(self, value):
        """Устанавливает invoice_details модели Payment.

        :param value: invoice_details модели Payment.
        :type value: PaymentInvoiceDetails
        """
        self.__invoice_details = PaymentInvoiceDetails(value)

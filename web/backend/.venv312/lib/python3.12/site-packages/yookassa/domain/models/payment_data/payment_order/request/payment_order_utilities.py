# coding: utf-8
import re  # noqa: F401

from yookassa.domain.models import Amount
from yookassa.domain.models.payment_data.payment_order.payment_order import PaymentOrder
from yookassa.domain.models.payment_data.payment_order.payment_order_recipient_utilities import PaymentOrderRecipientUtilities
from yookassa.domain.models.payment_data.payment_order.payment_order_type import PaymentOrderType
from yookassa.domain.models.payment_data.payment_order.payment_period import PaymentPeriod


class PaymentOrderUtilities(PaymentOrder):
    """Платежное поручение — распоряжение на перевод банку для оплаты жилищно-коммунальных услуг (ЖКУ), сведения о платеже для регистрации в ГИС ЖКХ.  Необходимо передавать при %[оплате ЖКУ](/developers/payment-acceptance/scenario-extensions/utility-payments).  Кроме параметров, отмеченных как обязательные, должен быть передан как минимум один параметр из этого списка: `payment_document_id`, `payment_document_number`, `account_number`, `unified_account_number` или `service_id`. """  # noqa: E501

    __amount = None
    """Сумма платежного поручения — сумма, которую пользователь переводит получателю платежа. Равна общей сумме платежа."""

    __payment_purpose = None
    """Назначение платежа (не больше 210 символов)."""

    __recipient = None
    """Получатель платежа — государственная или коммерческая организация, которая предоставляет услуги или является информационным посредником, который собирает и обрабатывает начисления от других поставщиков услуг."""

    __kbk = None
    """Код бюджетной классификации (КБК)."""  # noqa: E501

    __oktmo = None
    """Код ОКТМО (Общероссийский классификатор территорий муниципальных образований)."""  # noqa: E501

    __payment_period = None
    """Период оплаты, за который выставлены начисления и за который вносится оплата."""

    __payment_document_id = None
    """Идентификатор платежного документа.  Обязательный параметр, если не передан `payment_document_number`, `account_number`, `unified_account_number` или `service_id`. """  # noqa: E501

    __payment_document_number = None
    """Номер платежного документа на стороне поставщика ЖКУ.  Обязательный параметр, если не передан `payment_document_id`, `account_number`, `unified_account_number` или `service_id`. """  # noqa: E501

    __account_number = None
    """Номер лицевого счета на стороне поставщика ЖКУ.  Обязательный параметр, если не передан `payment_document_id`, `payment_document_number`, `unified_account_number` или `service_id`. """  # noqa: E501

    __unified_account_number = None
    """Единый лицевой счет. Уникальный идентификатор в ГИС ЖКХ, который характеризует связку «собственник-помещение».  Обязательный параметр, если не передан `payment_document_id`, `payment_document_number`, `account_number` или `service_id`. """  # noqa: E501

    __service_id = None
    """Идентификатор жилищно-коммунальной услуги (ЖКУ).  Обязательный параметр, если не передан `payment_document_id`, `payment_document_number`, `account_number` или `unified_account_number`. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentOrderUtilities, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentOrderType.UTILITIES:
            self.type = PaymentOrderType.UTILITIES

    @property
    def amount(self):
        """Возвращает amount модели PaymentOrderUtilities.

        :return: amount модели PaymentOrderUtilities.
        :rtype: Amount
        """
        return self.__amount

    @amount.setter
    def amount(self, value):
        """Устанавливает amount модели PaymentOrderUtilities.

        :param value: amount модели PaymentOrderUtilities.
        :type value: Amount
        """
        if isinstance(value, dict):
            self.__amount = Amount(value)
        elif isinstance(value, Amount):
            self.__amount = value
        else:
            raise TypeError('Invalid amount value type')

    @property
    def payment_purpose(self):
        """Возвращает payment_purpose модели PaymentOrderUtilities.

        :return: payment_purpose модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__payment_purpose

    @payment_purpose.setter
    def payment_purpose(self, value):
        """Устанавливает payment_purpose модели PaymentOrderUtilities.

        :param value: payment_purpose модели PaymentOrderUtilities.
        :type value: str
        """
        self.__payment_purpose = value

    @property
    def recipient(self):
        """Возвращает recipient модели PaymentOrderUtilities.

        :return: recipient модели PaymentOrderUtilities.
        :rtype: PaymentOrderRecipientUtilities
        """
        return self.__recipient

    @recipient.setter
    def recipient(self, value):
        """Устанавливает recipient модели PaymentOrderUtilities.

        :param value: recipient модели PaymentOrderUtilities.
        :type value: PaymentOrderRecipientUtilities
        """
        if isinstance(value, dict):
            self.__recipient = PaymentOrderRecipientUtilities(value)
        elif isinstance(value, PaymentOrderRecipientUtilities):
            self.__recipient = value
        else:
            raise TypeError('Invalid recipient data type in PaymentOrderUtilities.recipient')

    @property
    def kbk(self):
        """Возвращает kbk модели PaymentOrderUtilities.

        :return: kbk модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__kbk

    @kbk.setter
    def kbk(self, value):
        """Устанавливает kbk модели PaymentOrderUtilities.

        :param value: kbk модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 20:
            raise ValueError("Invalid value for `kbk`, length must be less than or equal to `20`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `kbk`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^(\d{20})|(0)$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `kbk`, must be a follow pattern or equal to `/(\d{20})|(0)/`")  # noqa: E501
        self.__kbk = value

    @property
    def oktmo(self):
        """Возвращает oktmo модели PaymentOrderUtilities.

        :return: oktmo модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__oktmo

    @oktmo.setter
    def oktmo(self, value):
        """Устанавливает oktmo модели PaymentOrderUtilities.

        :param value: oktmo модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 8:
            raise ValueError("Invalid value for `oktmo`, length must be less than or equal to `8`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `oktmo`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^(\d{8})|(0)$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `oktmo`, must be a follow pattern or equal to `/(\d{8})|(0)/`")  # noqa: E501
        self.__oktmo = value

    @property
    def payment_period(self):
        """Возвращает payment_period модели PaymentOrderUtilities.

        :return: payment_period модели PaymentOrderUtilities.
        :rtype: PaymentPeriod
        """
        return self.__payment_period

    @payment_period.setter
    def payment_period(self, value):
        """Устанавливает payment_period модели PaymentOrderUtilities.

        :param value: payment_period модели PaymentOrderUtilities.
        :type value: PaymentPeriod
        """
        if isinstance(value, dict):
            self.__payment_period = PaymentPeriod(value)
        elif isinstance(value, PaymentPeriod):
            self.__payment_period = value
        else:
            raise TypeError('Invalid payment_period data type in PaymentOrderUtilities.payment_period')

    @property
    def payment_document_id(self):
        """Возвращает payment_document_id модели PaymentOrderUtilities.

        :return: payment_document_id модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__payment_document_id

    @payment_document_id.setter
    def payment_document_id(self, value):
        """Устанавливает payment_document_id модели PaymentOrderUtilities.

        :param value: payment_document_id модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 18:
            raise ValueError("Invalid value for `payment_document_id`, length must be less than or equal to `18`")  # noqa: E501
        if value is not None and len(value) < 18:
            raise ValueError("Invalid value for `payment_document_id`, length must be greater than or equal to `18`")  # noqa: E501
        self.__payment_document_id = value

    @property
    def payment_document_number(self):
        """Возвращает payment_document_number модели PaymentOrderUtilities.

        :return: payment_document_number модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__payment_document_number

    @payment_document_number.setter
    def payment_document_number(self, value):
        """Устанавливает payment_document_number модели PaymentOrderUtilities.

        :param value: payment_document_number модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 30:
            raise ValueError("Invalid value for `payment_document_number`, length must be less than or equal to `30`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `payment_document_number`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^(.*)([0-9а-яА-Яa-zA-Z]+)(.*)$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `payment_document_number`, must be a follow pattern or equal to `/(.*)([0-9а-яА-Яa-zA-Z]+)(.*)/`")  # noqa: E501
        self.__payment_document_number = value

    @property
    def account_number(self):
        """Возвращает account_number модели PaymentOrderUtilities.

        :return: account_number модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__account_number

    @account_number.setter
    def account_number(self, value):
        """Устанавливает account_number модели PaymentOrderUtilities.

        :param value: account_number модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 30:
            raise ValueError("Invalid value for `account_number`, length must be less than or equal to `30`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `account_number`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^(.*)([0-9а-яА-Яa-zA-Z]+)(.*)$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `account_number`, must be a follow pattern or equal to `/(.*)([0-9а-яА-Яa-zA-Z]+)(.*)/`")  # noqa: E501
        self.__account_number = value

    @property
    def unified_account_number(self):
        """Возвращает unified_account_number модели PaymentOrderUtilities.

        :return: unified_account_number модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__unified_account_number

    @unified_account_number.setter
    def unified_account_number(self, value):
        """Устанавливает unified_account_number модели PaymentOrderUtilities.

        :param value: unified_account_number модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 10:
            raise ValueError("Invalid value for `unified_account_number`, length must be less than or equal to `10`")  # noqa: E501
        if value is not None and len(value) < 10:
            raise ValueError("Invalid value for `unified_account_number`, length must be greater than or equal to `10`")  # noqa: E501
        self.__unified_account_number = value

    @property
    def service_id(self):
        """Возвращает service_id модели PaymentOrderUtilities.

        :return: service_id модели PaymentOrderUtilities.
        :rtype: str
        """
        return self.__service_id

    @service_id.setter
    def service_id(self, value):
        """Устанавливает service_id модели PaymentOrderUtilities.

        :param value: service_id модели PaymentOrderUtilities.
        :type value: str
        """
        if value is not None and len(value) > 13:
            raise ValueError("Invalid value for `service_id`, length must be less than or equal to `13`")  # noqa: E501
        if value is not None and len(value) < 13:
            raise ValueError("Invalid value for `service_id`, length must be greater than or equal to `13`")  # noqa: E501
        self.__service_id = value



# coding: utf-8
from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodSms(DeliveryMethod):
    """Данные для выставления счета с доставкой ссылки на счет в смс."""  # noqa: E501

    __phone = None

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodSms, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.SMS:
            self.type = DeliveryMethodType.SMS

    @property
    def phone(self):
        """Возвращает phone модели DeliveryMethodSms.

        :return: phone модели DeliveryMethodSms.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """Устанавливает phone модели DeliveryMethodSms.

        :param value: phone модели DeliveryMethodSms.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `phone`, must not be `None`")  # noqa: E501
        self.__phone = value

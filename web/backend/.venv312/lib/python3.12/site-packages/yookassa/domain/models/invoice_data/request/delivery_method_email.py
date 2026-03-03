# coding: utf-8
import re  # noqa: F401

from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodEmail(DeliveryMethod):
    """Данные для выставления счета с отправкой по электронной почте."""  # noqa: E501

    __email = None

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodEmail, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.EMAIL:
            self.type = DeliveryMethodType.EMAIL

    @property
    def email(self):
        """Возвращает email модели DeliveryMethodEmail.

        :return: email модели DeliveryMethodEmail.
        :rtype: str
        """
        return self.__email

    @email.setter
    def email(self, value):
        """Устанавливает email модели DeliveryMethodEmail.

        :param value: email модели DeliveryMethodEmail.
        :type value: str
        """
        cast_value = str(value)
        if cast_value is None:  # noqa: E501
            raise ValueError("Invalid value for `email`, must not be `None`")  # noqa: E501
        elif re.match(r"^[^@]+@[^@]+\.[^@]+$", cast_value):
            self.__email = cast_value
        else:
            raise ValueError('Invalid email value type')

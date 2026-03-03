# -*- coding: utf-8 -*-
import re

from yookassa.domain.common import BaseObject


class ReceiptCustomer(BaseObject):
    """
    Информация о пользователе. Необходимо указать как минимум контактные данные: для Чеков от ЮKassa — электронную почту (`customer.email`), в остальных случаях — электронную почту (`customer.email`) или номер телефона (`customer.phone`). 
    """  # noqa: E501

    __full_name = None
    """Для юрлица — название организации, для ИП и физического лица — ФИО. Если у физлица отсутствует ИНН, в этом же параметре передаются паспортные данные. Не более 256 символов. <br/>Можно передавать, если используете Чеки от ЮKassa или онлайн-кассу Orange Data, Атол Онлайн. """  # noqa: E501

    __inn = None
    """ИНН плательщика (10 или 12 цифр)."""  # noqa: E501

    __email = None
    """E-mail адрес плательщика на который будет выслан чек."""  # noqa: E501

    __phone = None
    """Номер телефона плательщика в формате ITU-T E.164 на который будет выслан чек."""  # noqa: E501

    @property
    def full_name(self):
        """
        Возвращает full_name модели ReceiptCustomer.

        :return: full_name модели ReceiptCustomer.
        :rtype: str
        """
        return self.__full_name

    @full_name.setter
    def full_name(self, value):
        """
        Устанавливает full_name модели ReceiptCustomer.

        :param value: full_name модели ReceiptCustomer.
        :type value: str
        """
        self.__full_name = str(value)

    @property
    def inn(self):
        """
        Возвращает inn модели ReceiptCustomer.

        :return: inn модели ReceiptCustomer.
        :rtype: str
        """
        return self.__inn

    @inn.setter
    def inn(self, value):
        """
        Устанавливает inn модели ReceiptCustomer.

        :param value: inn модели ReceiptCustomer.
        :type value: str
        """
        self.__inn = str(value)

    @property
    def email(self):
        """
        Возвращает email модели ReceiptCustomer.

        :return: email модели ReceiptCustomer.
        :rtype: str
        """
        return self.__email

    @email.setter
    def email(self, value):
        """
        Устанавливает email модели ReceiptCustomer.

        :param value: email модели ReceiptCustomer.
        :type value: str
        """
        cast_value = str(value)
        if re.match(r"^[^@]+@[^@]+\.[^@]+$", cast_value):
            self.__email = cast_value
        else:
            raise ValueError('Invalid email value type')

    @property
    def phone(self):
        """
        Возвращает phone модели ReceiptCustomer.

        :return: phone модели ReceiptCustomer.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели ReceiptCustomer.

        :param value: phone модели ReceiptCustomer.
        :type value: str
        """
        self.__phone = str(value)

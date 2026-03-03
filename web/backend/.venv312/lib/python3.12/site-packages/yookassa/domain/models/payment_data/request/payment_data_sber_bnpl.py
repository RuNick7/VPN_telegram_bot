# coding: utf-8
import re

from yookassa.domain.common.payment_method_type import PaymentMethodType
from yookassa.domain.models.payment_data.payment_data import PaymentData


class PaymentDataSberBnpl(PaymentData):
    """
    Данные для оплаты через сервис «Плати частями».
    """  # noqa: E501

    __phone = None
    """Номер телефона пользователя. Передается партнеру и используется для авторизации в сервисе «Плати частями».
    Максимум 15 символов. Указывается в формате [ITU-T E.164](https://ru.wikipedia.org/wiki/E.164). Пример: ~`79000000000`."""  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(PaymentDataSberBnpl, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not PaymentMethodType.SBER_BNPL:
            self.type = PaymentMethodType.SBER_BNPL

    @property
    def phone(self):
        """Возвращает phone модели PaymentDataSberBnpl.

        :return: phone модели PaymentDataSberBnpl.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """Устанавливает phone модели PaymentDataSberBnpl.

        :param value: phone модели PaymentDataSberBnpl.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{4,15}$', cast_value):
            self.__phone = cast_value
        else:
            raise ValueError('Invalid phone value type')

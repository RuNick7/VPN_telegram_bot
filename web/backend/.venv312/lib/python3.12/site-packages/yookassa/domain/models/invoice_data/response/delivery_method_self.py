# coding: utf-8

from yookassa.domain.common import BaseObject
from yookassa.domain.models.invoice import DeliveryMethodType
from yookassa.domain.models.invoice_data.delivery_method import DeliveryMethod


class DeliveryMethodSelf(DeliveryMethod):
    """Данные для самостоятельной доставки пользователю ссылки на счет."""  # noqa: E501

    __url = None
    """URL страницы счета, который необходимо передать пользователю для оплаты. Не более 2048 символов. """  # noqa: E501

    def __init__(self, *args, **kwargs):
        super(DeliveryMethodSelf, self).__init__(*args, **kwargs)
        if self.type is None or self.type is not DeliveryMethodType.SELF:
            self.type = DeliveryMethodType.SELF

    @property
    def url(self):
        """Возвращает url модели DeliveryMethodSelf.

        :return: url модели DeliveryMethodSelf.
        :rtype: str
        """
        return self.__url

    @url.setter
    def url(self, value):
        """Устанавливает url модели DeliveryMethodSelf.

        :param value: url модели DeliveryMethodSelf.
        :type value: str
        """
        self.__url = value


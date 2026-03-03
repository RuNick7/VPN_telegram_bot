# -*- coding: utf-8 -*-
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.self_employed_data.confirmation import SelfEmployedConfirmation
from yookassa.domain.models.self_employed_data.confirmation_factory import SelfEmployedConfirmationFactory

DESCRIPTION_MAX_LENGTH = 128


class SelfEmployedRequest(RequestObject):
    """
    Объект запроса к API на создание объекта самозанятого.
    """  # noqa: E501

    __itn = None
    """ИНН самозанятого. Формат: 12 цифр без пробелов. Обязательный параметр, если не передан phone."""  # noqa: E501

    __phone = None
    """Телефон самозанятого, который привязан к личному кабинету в сервисе Мой налог."""  # noqa: E501

    __confirmation = None
    """Сценарий подтверждения пользователем заявки ЮMoney на получение прав для регистрации чеков в сервисе Мой налог."""  # noqa: E501

    __description = None
    """Описание к созданию самозанятого."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def itn(self):
        """
        Возвращает itn модели SelfEmployedRequest.

        :return: itn модели SelfEmployedRequest.
        :rtype: str
        """
        return self.__itn

    @itn.setter
    def itn(self, value):
        """
        Устанавливает itn модели SelfEmployedRequest.

        :param value: itn модели SelfEmployedRequest.
        :type value: str
        """
        self.__itn = value

    @property
    def phone(self):
        """
        Возвращает phone модели SelfEmployedRequest.

        :return: phone модели SelfEmployedRequest.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели SelfEmployedRequest.

        :param value: phone модели SelfEmployedRequest.
        :type value: str
        """
        self.__phone = str(value)

    @property
    def confirmation(self):
        """
        Возвращает confirmation модели SelfEmployedRequest.

        :return: confirmation модели SelfEmployedRequest.
        :rtype: SelfEmployedConfirmation
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """
        Устанавливает confirmation модели SelfEmployedRequest.

        :param value: confirmation модели SelfEmployedRequest.
        :type value: SelfEmployedConfirmation
        """
        if isinstance(value, dict):
            self.__confirmation = SelfEmployedConfirmationFactory().create(value, self.context())
        elif isinstance(value, SelfEmployedConfirmation):
            self.__confirmation = value
        else:
            raise TypeError('Invalid confirmation data type in SelfEmployedRequest.confirmation')

    @property
    def description(self):
        """
        Возвращает description модели SelfEmployedRequest.

        :return: description модели SelfEmployedRequest.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели SelfEmployedRequest.

        :param value: description модели SelfEmployedRequest.
        :type value: str
        """
        if value is not None and len(value) > DESCRIPTION_MAX_LENGTH:
            raise ValueError("Invalid value for `description`, length must be less than or equal to `{}`".format(DESCRIPTION_MAX_LENGTH))  # noqa: E501
        self.__description = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели SelfEmployedRequest.

        :return: metadata модели SelfEmployedRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели SelfEmployedRequest.

        :param value: metadata модели SelfEmployedRequest.
        :type value: dict[str, str]
        """
        self.__metadata = value

    def validate(self):
        """
        Валидация данных модели SelfEmployedRequest.
        """
        if self.itn is None and self.phone is None:
            self.__set_validation_error('Both itn and phone values are empty in self_employed_request')

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели SelfEmployedRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

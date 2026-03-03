# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import ResponseObject
from yookassa.domain.models.self_employed_data.confirmation_factory import SelfEmployedConfirmationFactory


class SelfEmployedResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о самозанятом.
    """  # noqa: E501

    __id = None
    """Идентификатор самозанятого в ЮKassa."""  # noqa: E501

    __status = None
    """Статус подключения самозанятого и выдачи ЮMoney прав на регистрацию чеков."""  # noqa: E501

    __created_at = None
    """Время создания объекта самозанятого. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __itn = None
    """ИНН самозанятого."""  # noqa: E501

    __phone = None
    """Телефон самозанятого, который привязан к личному кабинету в сервисе Мой налог."""  # noqa: E501

    __confirmation = None
    """Сценарий подтверждения пользователем заявки ЮMoney на получение прав для регистрации чеков в сервисе Мой налог."""  # noqa: E501

    __description = None
    """Описание к созданию самозанятого."""

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __test = None
    """Признак тестовой операции."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели SelfEmployedResponse.

        :return: id модели SelfEmployedResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели SelfEmployedResponse.

        :param value: id модели SelfEmployedResponse.
        :type value: str
        """
        self.__id = value

    @property
    def status(self):
        """
        Возвращает status модели SelfEmployedResponse.

        :return: status модели SelfEmployedResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели SelfEmployedResponse.

        :param value: status модели SelfEmployedResponse.
        :type value: str
        """
        self.__status = str(value)

    @property
    def created_at(self):
        """
        Возвращает created_at модели SelfEmployedResponse.

        :return: created_at модели SelfEmployedResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели SelfEmployedResponse.

        :param value: created_at модели SelfEmployedResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def itn(self):
        """
        Возвращает itn модели SelfEmployedResponse.

        :return: itn модели SelfEmployedResponse.
        :rtype: str
        """
        return self.__itn

    @itn.setter
    def itn(self, value):
        """
        Устанавливает itn модели SelfEmployedResponse.

        :param value: itn модели SelfEmployedResponse.
        :type value: str
        """
        self.__itn = value

    @property
    def phone(self):
        """
        Возвращает phone модели SelfEmployedResponse.

        :return: phone модели SelfEmployedResponse.
        :rtype: str
        """
        return self.__phone

    @phone.setter
    def phone(self, value):
        """
        Устанавливает phone модели SelfEmployedResponse.

        :param value: phone модели SelfEmployedResponse.
        :type value: str
        """
        self.__phone = str(value)

    @property
    def confirmation(self):
        """
        Возвращает confirmation модели SelfEmployedResponse.

        :return: confirmation модели SelfEmployedResponse.
        :rtype: SelfEmployedConfirmation
        """
        return self.__confirmation

    @confirmation.setter
    def confirmation(self, value):
        """
        Устанавливает confirmation модели SelfEmployedResponse.

        :param value: confirmation модели SelfEmployedResponse.
        :type value: SelfEmployedConfirmation
        """
        self.__confirmation = SelfEmployedConfirmationFactory().create(value, self.context())

    @property
    def description(self):
        """
        Возвращает description модели SelfEmployedResponse.

        :return: description модели SelfEmployedResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели SelfEmployedResponse.

        :param value: description модели SelfEmployedResponse.
        :type value: str
        """
        self.__description = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели SelfEmployedResponse.

        :return: metadata модели SelfEmployedResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели SelfEmployedResponse.

        :param value: metadata модели SelfEmployedResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

    @property
    def test(self):
        """
        Возвращает test модели SelfEmployedResponse.

        :return: test модели SelfEmployedResponse.
        :rtype: bool
        """
        return self.__test

    @test.setter
    def test(self, value):
        """
        Устанавливает test модели SelfEmployedResponse.

        :param value: test модели SelfEmployedResponse.
        :type value: bool
        """
        self.__test = value

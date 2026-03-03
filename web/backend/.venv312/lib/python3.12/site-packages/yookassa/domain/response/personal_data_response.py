# coding: utf-8
from yookassa.domain.common.response_object import ResponseObject
from yookassa.domain.models import CancellationDetails


class PersonalDataResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе информации о персональных данных.
    """  # noqa: E501

    __id = None
    """Идентификатор персональных данных, сохраненных в ЮKassa."""  # noqa: E501

    __type = None
    """Тип персональных данных."""  # noqa: E501

    __status = None
    """Статус персональных данных. Возможные значения:  * ~`waiting_for_operation` — данные сохранены, но не использованы при проведении выплаты; * ~`active` — данные сохранены и использованы при проведении выплаты; данные можно использовать повторно до срока, указанного в параметре `expires_at`; * ~`canceled` — хранение данных отменено, данные удалены, инициатор и причина отмены указаны в объекте `cancellation_details` (финальный и неизменяемый статус).  %[Подробнее о жизненном цикле персональных данных](/developers/payouts/scenario-extensions/recipient-check#lifecircle) """  # noqa: E501

    __cancellation_details = None
    """Комментарий к отмене выплаты."""  # noqa: E501

    __created_at = None
    """Время создания персональных данных. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __expires_at = None
    """Срок жизни объекта персональных данных — время, до которого вы можете использовать персональные данные при проведении операций. Указывается только для объекта в статусе ~`active`. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PersonalDataResponse.

        :return: id модели PersonalDataResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PersonalDataResponse.

        :param value: id модели PersonalDataResponse.
        :type value: str
        """
        self.__id = value

    @property
    def type(self):
        """
        Возвращает type модели PersonalDataResponse.

        :return: type модели PersonalDataResponse.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели PersonalDataResponse.

        :param value: type модели PersonalDataResponse.
        :type value: str
        """
        self.__type = value

    @property
    def status(self):
        """
        Возвращает status модели PersonalDataResponse.

        :return: status модели PersonalDataResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели PersonalDataResponse.

        :param value: status модели PersonalDataResponse.
        :type value: str
        """
        self.__status = value

    @property
    def cancellation_details(self):
        """
        Возвращает cancellation_details модели PersonalDataResponse.

        :return: cancellation_details модели PersonalDataResponse.
        :rtype: CancellationDetails
        """
        return self.__cancellation_details

    @cancellation_details.setter
    def cancellation_details(self, value):
        """
        Устанавливает cancellation_details модели PersonalDataResponse.

        :param value: cancellation_details модели PersonalDataResponse.
        :type value: CancellationDetails
        """
        self.__cancellation_details = CancellationDetails(value)

    @property
    def created_at(self):
        """
        Возвращает created_at модели PersonalDataResponse.

        :return: created_at модели PersonalDataResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели PersonalDataResponse.

        :param value: created_at модели PersonalDataResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def expires_at(self):
        """
        Возвращает expires_at модели PersonalDataResponse.

        :return: expires_at модели PersonalDataResponse.
        :rtype: datetime
        """
        return self.__expires_at

    @expires_at.setter
    def expires_at(self, value):
        """
        Устанавливает expires_at модели PersonalDataResponse.

        :param value: expires_at модели PersonalDataResponse.
        :type value: datetime
        """
        self.__expires_at = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели PersonalDataResponse.

        :return: metadata модели PersonalDataResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PersonalDataResponse.

        :param value: metadata модели PersonalDataResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

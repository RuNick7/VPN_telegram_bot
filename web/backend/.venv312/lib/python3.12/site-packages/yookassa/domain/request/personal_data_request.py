# coding: utf-8
import datetime
import re  # noqa: F401

from yookassa.domain.common import TypeFactory, DataContext
from yookassa.domain.common.request_object import RequestObject
from yookassa.domain.models.personal_data import PersonalDataType


class PayoutStatementRecipientPersonalDataRequest(RequestObject):
    """
    Объект запроса к API на создание персональных данных.
    """  # noqa: E501

    __type = None
    """Значение — payout_statement_recipient. Тип персональных данных."""  # noqa: E501

    __last_name = None
    """Фамилия пользователя."""  # noqa: E501

    __first_name = None
    """Имя пользователя."""  # noqa: E501

    __middle_name = None
    """Отчество пользователя. Обязательный параметр, если есть в паспорте."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    __birthdate = None
    """Дата рождения. Передается в формате ISO 8601"""  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели PayoutStatementRecipientPersonalDataRequest.

        :return: type модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели PayoutStatementRecipientPersonalDataRequest.

        :param value: type модели PayoutStatementRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = str(value)

    @property
    def last_name(self):
        """
        Возвращает last_name модели PayoutStatementRecipientPersonalDataRequest.

        :return: last_name модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__last_name

    @last_name.setter
    def last_name(self, value):
        """
        Устанавливает last_name модели PayoutStatementRecipientPersonalDataRequest.

        :param value: last_name модели PayoutStatementRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `last_name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 200:
            raise ValueError("Invalid value for `last_name`, length must be less than or equal to `200`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `last_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `last_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__last_name = value

    @property
    def first_name(self):
        """
        Возвращает first_name модели PayoutStatementRecipientPersonalDataRequest.

        :return: first_name модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__first_name

    @first_name.setter
    def first_name(self, value):
        """
        Устанавливает first_name модели PayoutStatementRecipientPersonalDataRequest.

        :param value: first_name модели PayoutStatementRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `first_name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 100:
            raise ValueError("Invalid value for `first_name`, length must be less than or equal to `100`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `first_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `first_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__first_name = value

    @property
    def middle_name(self):
        """
        Возвращает middle_name модели PayoutStatementRecipientPersonalDataRequest.

        :return: middle_name модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__middle_name

    @middle_name.setter
    def middle_name(self, value):
        """
        Устанавливает middle_name модели PayoutStatementRecipientPersonalDataRequest.

        :param value: middle_name модели PayoutStatementRecipientPersonalDataRequest.
        :type value: str
        """
        if value is not None and len(value) > 200:
            raise ValueError("Invalid value for `middle_name`, length must be less than or equal to `200`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `middle_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `middle_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__middle_name = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели PayoutStatementRecipientPersonalDataRequest.

        :return: metadata модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели PayoutStatementRecipientPersonalDataRequest.

        :param value: metadata модели PayoutStatementRecipientPersonalDataRequest.
        :type value: dict[str, str]
        """
        self.__metadata = value

    @property
    def birthdate(self):
        """
        Возвращает birthdate модели PayoutStatementRecipientPersonalDataRequest.

        :return: birthdate модели PayoutStatementRecipientPersonalDataRequest.
        :rtype: datetime
        """
        return self.__birthdate

    @birthdate.setter
    def birthdate(self, value):
        """
        Устанавливает metadata модели PayoutStatementRecipientPersonalDataRequest.

        :param value: metadata модели PayoutStatementRecipientPersonalDataRequest.
        :type value: str
        """
        try:
            datetime.datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Incorrect data format, should be YYYY-MM-DD")

        self.__birthdate = value


    def validate(self):
        """
        Влидация данных модели PayoutStatementRecipientPersonalDataRequest.
        """
        if self.type is None or self.last_name is None or self.first_name is None or self.birthdate is None:
            self.__set_validation_error('Type, last_name, first_name and birthdate values cannot be empty in PayoutStatementRecipientPersonalDataRequest')  # noqa: E501

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели PayoutStatementRecipientPersonalDataRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)

class SbpPayoutRecipientPersonalDataRequest(RequestObject):

    __type = None
    """Тип персональных данных."""  # noqa: E501

    __last_name = None
    """Фамилия пользователя."""  # noqa: E501

    __first_name = None
    """Имя пользователя."""  # noqa: E501

    __middle_name = None
    """Отчество пользователя. Обязательный параметр, если есть в паспорте."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def type(self):
        """
        Возвращает type модели SbpPayoutRecipientPersonalDataRequest.

        :return: type модели SbpPayoutRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__type

    @type.setter
    def type(self, value):
        """
        Устанавливает type модели SbpPayoutRecipientPersonalDataRequest.

        :param value: type модели SbpPayoutRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        self.__type = str(value)

    @property
    def last_name(self):
        """
        Возвращает last_name модели SbpPayoutRecipientPersonalDataRequest.

        :return: last_name модели SbpPayoutRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__last_name

    @last_name.setter
    def last_name(self, value):
        """
        Устанавливает last_name модели SbpPayoutRecipientPersonalDataRequest.

        :param value: last_name модели SbpPayoutRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `last_name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 200:
            raise ValueError("Invalid value for `last_name`, length must be less than or equal to `200`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `last_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `last_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__last_name = value

    @property
    def first_name(self):
        """
        Возвращает first_name модели SbpPayoutRecipientPersonalDataRequest.

        :return: first_name модели SbpPayoutRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__first_name

    @first_name.setter
    def first_name(self, value):
        """
        Устанавливает first_name модели SbpPayoutRecipientPersonalDataRequest.

        :param value: first_name модели SbpPayoutRecipientPersonalDataRequest.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `first_name`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 100:
            raise ValueError("Invalid value for `first_name`, length must be less than or equal to `100`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `first_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `first_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__first_name = value

    @property
    def middle_name(self):
        """
        Возвращает middle_name модели SbpPayoutRecipientPersonalDataRequest.

        :return: middle_name модели SbpPayoutRecipientPersonalDataRequest.
        :rtype: str
        """
        return self.__middle_name

    @middle_name.setter
    def middle_name(self, value):
        """
        Устанавливает middle_name модели SbpPayoutRecipientPersonalDataRequest.

        :param value: middle_name модели SbpPayoutRecipientPersonalDataRequest.
        :type value: str
        """
        if value is not None and len(value) > 200:
            raise ValueError("Invalid value for `middle_name`, length must be less than or equal to `200`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `middle_name`, length must be greater than or equal to `1`")  # noqa: E501
        if value is not None and not re.search(r'^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$', value):  # noqa: E501
            raise ValueError(r"Invalid value for `middle_name`, must be a follow pattern or equal to `/^[—–‐\-a-zA-Zа-яёА-ЯЁ ]*$/`")  # noqa: E501
        self.__middle_name = value

    @property
    def metadata(self):
        """
        Возвращает metadata модели SbpPayoutRecipientPersonalDataRequest.

        :return: metadata модели SbpPayoutRecipientPersonalDataRequest.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели SbpPayoutRecipientPersonalDataRequest.

        :param value: metadata модели SbpPayoutRecipientPersonalDataRequest.
        :type value: dict[str, str]
        """
        self.__metadata = value

    def validate(self):
        """
        Влидация данных модели SbpPayoutRecipientPersonalDataRequest.
        """
        if self.type is None or self.last_name is None or self.first_name is None:
            self.__set_validation_error('Type, last_name and first_name values cannot be empty in SbpPayoutRecipientPersonalDataRequest')  # noqa: E501

    def __set_validation_error(self, message):
        """
        Устанавливает message в Exception при валидации модели SbpPayoutRecipientPersonalDataRequest.

        :param message: message модели Exception.
        :type message: str
        """
        raise ValueError(message)


class PersonalDataRequestClassMap(DataContext):
    """
    Сопоставление классов PersonalDataRequest по типу.
    """  # noqa: E501

    def __init__(self):
        super(PersonalDataRequestClassMap, self).__init__(('request'))

    @property
    def request(self):
        return {
            PersonalDataType.PAYOUT_STATEMENT_RECIPIENT: PayoutStatementRecipientPersonalDataRequest,
            PersonalDataType.SBP_PAYOUT_RECIPIENT: SbpPayoutRecipientPersonalDataRequest,
        }


class PersonalDataRequestFactory(TypeFactory):
    """
    Фабрика создания объекта PersonalDataRequest по типу.
    """  # noqa: E501

    def __init__(self):
        super(PersonalDataRequestFactory, self).__init__(PersonalDataRequestClassMap())

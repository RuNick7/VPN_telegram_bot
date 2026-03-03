# -*- coding: utf-8 -*-
from yookassa.domain.common import ResponseObject
from yookassa.domain.models import Amount


class DealResponse(ResponseObject):
    """
    Объект ответа, возвращаемого API при запросе конкретной сделки.
    """  # noqa: E501

    __id = None
    """Идентификатор сделки."""  # noqa: E501

    __type = None
    """Тип сделки. Фиксированное значение: ~`safe_deal` — Безопасная сделка. """  # noqa: E501

    __status = None
    """Статус сделки."""  # noqa: E501

    __balance = None
    """Баланс сделки."""  # noqa: E501

    __payout_balance = None
    """Сумма вознаграждения продавцаю."""  # noqa: E501

    __description = None
    """Описание сделки (не более 128 символов). Используется для фильтрации при [получении списка сделок](/developers/api#get_deals_list). """  # noqa: E501

    __fee_moment = None
    """Момент перечисления вам вознаграждения платформы."""  # noqa: E501

    __created_at = None
    """Время создания сделки. Указывается по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __expires_at = None
    """Время автоматического закрытия сделки. Если в указанное время сделка всё еще в статусе ~`opened`, ЮKassa вернет деньги покупателю и закроет сделку. По умолчанию время жизни сделки составляет 90 дней. Время указывается  по [UTC](https://ru.wikipedia.org/wiki/Всемирное_координированное_время) и передается в формате [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601). Пример: ~`2017-11-03T11:52:31.827Z` """  # noqa: E501

    __test = None
    """Признак тестовой операции."""  # noqa: E501

    __metadata = None
    """Любые дополнительные данные, которые нужны вам для работы (например, ваш внутренний идентификатор заказа). Передаются в виде набора пар «ключ-значение» и возвращаются в ответе от ЮKassa. Ограничения: максимум 16 ключей, имя ключа не больше 32 символов, значение ключа не больше 512 символов, тип данных — строка в формате UTF-8. """  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели DealResponse.

        :return: id модели DealResponse.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели DealResponse.

        :param value: id модели DealResponse.
        :type value: str
        """
        self.__id = value

    @property
    def status(self):
        """
        Возвращает status модели DealResponse.

        :return: status модели DealResponse.
        :rtype: str
        """
        return self.__status

    @status.setter
    def status(self, value):
        """
        Устанавливает status модели DealResponse.

        :param value: status модели DealResponse.
        :type value: str
        """
        self.__status = value

    @property
    def balance(self):
        """
        Возвращает balance модели DealResponse.

        :return: balance модели DealResponse.
        :rtype: Amount
        """
        return self.__balance

    @balance.setter
    def balance(self, value):
        """
        Устанавливает balance модели DealResponse.

        :param value: balance модели DealResponse.
        :type value: Amount
        """
        self.__balance = Amount(value)

    @property
    def payout_balance(self):
        """
        Возвращает payout_balance модели DealResponse.

        :return: payout_balance модели DealResponse.
        :rtype: Amount
        """
        return self.__payout_balance

    @payout_balance.setter
    def payout_balance(self, value):
        """
        Устанавливает payout_balance модели DealResponse.

        :param value: payout_balance модели DealResponse.
        :type value: Amount
        """
        self.__payout_balance = Amount(value)

    @property
    def description(self):
        """
        Возвращает description модели DealResponse.

        :return: description модели DealResponse.
        :rtype: str
        """
        return self.__description

    @description.setter
    def description(self, value):
        """
        Устанавливает description модели DealResponse.

        :param value: description модели DealResponse.
        :type value: str
        """
        self.__description = value

    @property
    def fee_moment(self):
        """
        Возвращает fee_moment модели DealResponse.

        :return: fee_moment модели DealResponse.
        :rtype: str
        """
        return self.__fee_moment

    @fee_moment.setter
    def fee_moment(self, value):
        """
        Устанавливает fee_moment модели DealResponse.

        :param value: fee_moment модели DealResponse.
        :type value: str
        """
        self.__fee_moment = str(value)

    @property
    def created_at(self):
        """
        Возвращает created_at модели DealResponse.

        :return: created_at модели DealResponse.
        :rtype: datetime
        """
        return self.__created_at

    @created_at.setter
    def created_at(self, value):
        """
        Устанавливает created_at модели DealResponse.

        :param value: created_at модели DealResponse.
        :type value: datetime
        """
        self.__created_at = value

    @property
    def expires_at(self):
        """
        Возвращает expires_at модели DealResponse.

        :return: expires_at модели DealResponse.
        :rtype: datetime
        """
        return self.__expires_at

    @expires_at.setter
    def expires_at(self, value):
        """
        Устанавливает expires_at модели DealResponse.

        :param value: expires_at модели DealResponse.
        :type value: datetime
        """
        self.__expires_at = value

    @property
    def test(self):
        """
        Возвращает test модели DealResponse.

        :return: test модели DealResponse.
        :rtype: bool
        """
        return self.__test

    @test.setter
    def test(self, value):
        """
        Устанавливает test модели DealResponse.

        :param value: test модели DealResponse.
        :type value: bool
        """
        self.__test = bool(value)

    @property
    def metadata(self):
        """
        Возвращает metadata модели DealResponse.

        :return: metadata модели DealResponse.
        :rtype: dict[str, str]
        """
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        """
        Устанавливает metadata модели DealResponse.

        :param value: metadata модели DealResponse.
        :type value: dict[str, str]
        """
        self.__metadata = value

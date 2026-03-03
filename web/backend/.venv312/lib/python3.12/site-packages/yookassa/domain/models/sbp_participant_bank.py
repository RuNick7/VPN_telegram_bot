# coding: utf-8
from yookassa.domain.common import BaseObject


class SbpParticipantBank(BaseObject):
    """
    Объект участника СБП (Системы быстрых платежей ЦБ РФ) — актуальная информация о банке или платежном сервисе, подключенном к СБП.
    """  # noqa: E501

    __bank_id = None
    """Идентификатор банка или платежного сервиса в СБП."""  # noqa: E501

    __name = None
    """Название банка или платежного сервиса в СБП."""  # noqa: E501

    __bic = None
    """Банковский идентификационный код (БИК) банка или платежного сервиса."""  # noqa: E501

    @property
    def bank_id(self):
        """
        Возвращает bank_id модели SbpParticipantBank.

        :return: bank_id модели SbpParticipantBank.
        :rtype: str
        """
        return self.__bank_id

    @bank_id.setter
    def bank_id(self, value):
        """
        Устанавливает bank_id модели SbpParticipantBank.

        :param value: bank_id модели SbpParticipantBank.
        :type value: str
        """
        self.__bank_id = str(value)

    @property
    def name(self):
        """
        Возвращает name модели SbpParticipantBank.

        :return: name модели SbpParticipantBank.
        :rtype: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Устанавливает name модели SbpParticipantBank.

        :param value: name модели SbpParticipantBank.
        :type value: str
        """
        self.__name = str(value)

    @property
    def bic(self):
        """
        Возвращает bic модели SbpParticipantBank.

        :return: bic модели SbpParticipantBank.
        :rtype: str
        """
        return self.__bic

    @bic.setter
    def bic(self, value):
        """
        Устанавливает bic модели SbpParticipantBank.

        :param value: bic модели SbpParticipantBank.
        :type value: str
        """
        self.__bic = str(value)
